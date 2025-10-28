import asyncio, importlib.resources
from typing import Any, Literal
from pydantic import BaseModel
from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, Composer, HTTPContext, WebsocketContext, http_handler, http_not_found_handler, routed_handler, websocket_handler
from rxxxt.elements import ElementFactory
from rxxxt.execution import InputEvent
from rxxxt.page import PageFactory, default_page
from rxxxt.session import AppConfig, Session, SessionConfig
from rxxxt.state import StateResolver, default_state_resolver

class AppHttpRequest(BaseModel):
  state_token: str
  events: tuple[InputEvent, ...]

class AppWebsocketInitMessage(BaseModel):
  type: Literal["init"]
  state_token: str
  enable_state_updates: bool

class AppWebsocketUpdateMessage(BaseModel):
  type: Literal["update"]
  events: tuple[InputEvent, ...]
  location: str

class App:
  def __init__(self, content: ElementFactory, state_resolver: StateResolver | None = None, page_factory: PageFactory = default_page, \
      config: AppConfig | None = None) -> None:
    self._content = content
    self._page_factory: PageFactory = page_factory
    self._state_resolver = state_resolver or default_state_resolver()
    self._composer = Composer()
    self._config = config or AppConfig()
    _ = self._composer.add_handler(http_handler(routed_handler("/rxxxt-client.js")(self._http_static_rxxxt_client_js)))
    _ = self._composer.add_handler(http_handler(self._http_post_session))
    _ = self._composer.add_handler(http_handler(self._http_get_session))
    _ = self._composer.add_handler(websocket_handler(self._ws_session))
    _ = self._composer.add_handler(http_not_found_handler)

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    return await self._composer(scope, receive, send)

  async def _ws_session(self, context: WebsocketContext):
    updating_lock = asyncio.Lock()
    session = self._create_session(True)
    try:
      await context.setup()
      message = await context.receive_message()
      init_message = AppWebsocketInitMessage.model_validate_json(message)

      await session.init(init_message.state_token)
      session.set_location(context.location)
      session.set_headers(context.headers)

      async def updater():
        while True:
          await session.wait_for_update()
          async with updating_lock:
            await session.update()
            include_state_token = init_message.enable_state_updates or session.execution.is_websocket_closing
            data = await session.render_update(include_state_token=include_state_token, render_full=False)
            await context.send_message(data.model_dump_json(exclude_defaults=True))

      async def receiver():
        while True:
          message = await context.receive_message()
          async with updating_lock:
            update_message = AppWebsocketUpdateMessage.model_validate_json(message)
            session.set_location(update_message.location)
            await session.handle_events(update_message.events)

      async with asyncio.TaskGroup() as task_group:
        _ = task_group.create_task(receiver())
        _ = task_group.create_task(updater())

    except ConnectionError: pass
    except ExceptionGroup as eg:
      _, remaining_eg = eg.split(ConnectionError)
      if remaining_eg is not None:
        raise remaining_eg
    finally:
      await session.destroy()

  async def _http_post_session(self, context: HTTPContext):
    if context.method != "POST": context.next()
    async with self._create_session(False) as session:
      req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
      await session.init(req.state_token)
      session.set_location(context.location)
      session.set_headers(context.headers)
      await session.handle_events(req.events)
      await session.update(optional=True)
      result = await session.render_update(include_state_token=True, render_full=False)
      await context.respond_text(result.model_dump_json(exclude_defaults=True), mime_type="application/json")

  async def _http_get_session(self, context: HTTPContext):
    if context.method != "GET": context.next()
    async with self._create_session(False) as session:
      session.set_location(context.location)
      session.set_headers(context.headers)
      await session.init(None)
      await session.update(optional=True)
      result = await session.render_page(context.path)
      await context.respond_text(result, mime_type="text/html")

  async def _http_static_rxxxt_client_js(self, context: HTTPContext, _: dict[str, str]):
    with importlib.resources.path("rxxxt.assets", "main.js") as file_path:
      return await context.respond_file(file_path, use_last_modified=True)

  def _create_session(self, persistent: bool):
    config = SessionConfig(page_facotry=self._page_factory, state_resolver=self._state_resolver, persistent=persistent, app_config=self._config)
    return Session(config, self._content())
