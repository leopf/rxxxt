import asyncio
import contextlib
import importlib.resources
import logging
from typing import Any, Literal
from pydantic import BaseModel, ValidationError
from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext, WebsocketContext
from rxxxt.elements import ElementFactory
from rxxxt.events import InputEvent
from rxxxt.page import PageFactory, default_page
from rxxxt.session import Session, SessionConfig
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
  def __init__(self, content: ElementFactory, state_resolver: StateResolver | None = None, page_factory: PageFactory = default_page) -> None:
    self._content = content
    self._page_factory: PageFactory = page_factory
    self._state_resolver = state_resolver or default_state_resolver()

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] == "http":
      context = HTTPContext(scope, receive, send)
      try: await self._handle_http(context)
      except asyncio.CancelledError: raise
      except (ValidationError, ValueError) as e:
        logging.debug(e)
        return await context.respond_text("bad request", 400)
      except BaseException as e:
        logging.debug(e)
        return await context.respond_text("internal server error", 500)
    elif scope["type"] == "websocket":
      context = WebsocketContext(scope, receive, send)
      try: await self._ws_session(context)
      except asyncio.CancelledError: raise
      except BaseException as e:
        logging.debug(e)
        await context.close(1011, "Internal error")
      finally:
        if context.connected: await context.close()

  async def _ws_session(self, context: WebsocketContext):
    await context.setup()
    message = await context.receive_message()
    init_message = AppWebsocketInitMessage.model_validate_json(message)

    with contextlib.suppress(ConnectionError):
      async with Session(self._get_session_config(True), self._content()) as session:
        updating_lock = asyncio.Lock()

        async def updater():
          while context.connected:
            await session.wait_for_update()
            async with updating_lock:
              await session.update()
              data = await session.render_update(include_state_token=init_message.enable_state_updates, render_full=False)
              await context.send_message(data.model_dump_json(exclude_defaults=True))

        await session.init(init_message.state_token)

        session.set_location(context.location)
        session.set_headers(context.headers)

        updater_task = asyncio.create_task(updater())
        try:
          while True:
            message = await context.receive_message()
            async with updating_lock:
              update_message = AppWebsocketUpdateMessage.model_validate_json(message)
              session.set_location(update_message.location)
              await session.handle_events(update_message.events)
        finally: _ = updater_task.cancel()

  async def _http_session(self, context: HTTPContext):
    async with Session(self._get_session_config(False), self._content()) as session:

      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        await session.init(req.state_token)
        events = req.events
      else:
        session.set_location(context.location)
        await session.init(None)
        events = ()

      session.set_location(context.location)
      session.set_headers(context.headers)

      await session.handle_events(events)
      await session.update()

      if context.method == "POST":
        result = await session.render_update(include_state_token=True, render_full=False)
        await context.respond_text(result.model_dump_json(exclude_defaults=True), mime_type="application/json")
      else:
        result = await session.render_page(context.path)
        await context.respond_text(result, mime_type="text/html")

  async def _handle_http(self, context: HTTPContext):
    if context.path == "/rxxxt-client.js":
      with importlib.resources.path("rxxxt.assets", "main.js") as file_path:
        await context.respond_file(file_path)
    elif context.method in [ "GET", "POST" ]: await self._http_session(context)
    else: await context.respond_text("not found", 404)

  def _get_session_config(self, persistent: bool):
    return SessionConfig(page_facotry=self._page_factory, state_resolver=self._state_resolver, persistent=persistent)
