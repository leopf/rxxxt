import importlib.resources
import logging
from typing import Any, Literal
from pydantic import BaseModel, ValidationError
from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext, WebsocketContext
from rxxxt.elements import CustomAttribute as CustomAttribute, ElementFactory
from rxxxt.execution import InputEvent
from rxxxt.page import PageFactory, default_page
from rxxxt.session import Session, SessionConfig
from rxxxt.state import StateResolver, default_state_resolver

class AppHttpRequest(BaseModel):
  state_token: str
  events: list[InputEvent]

class AppWebsocketInitMessage(BaseModel):
  type: Literal["init"]
  state_token: str
  enableStateUpdates: bool

class AppWebsocketUpdateMessage(BaseModel):
  type: Literal["update"]
  events: list[InputEvent]
  location: str

  @property
  def path(self): return self.location.split("?")[0]

  @property
  def query_string(self):
    parts = self.location.split("?")
    return parts[1] if len(parts) > 1 else None

class App:
  def __init__(self, content: ElementFactory, state_resolver: StateResolver | None = None, page_layout: PageFactory = default_page) -> None:
    self.content = content
    self.page_layout: PageFactory = page_layout
    self.state_resolver = state_resolver or default_state_resolver()

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] == "http":
      context = HTTPContext(scope, receive, send)
      try: await self._handle_http(context)
      except (ValidationError, ValueError) as e:
        import traceback
        traceback.print_exc()
        logging.debug(e)
        return await context.respond_status(400)
      except BaseException as e:
        import traceback
        traceback.print_exc()
        logging.debug(e)
        return await context.respond_status(500)
    elif scope["type"] == "websocket":
      context = WebsocketContext(scope, receive, send)
      try: await self._ws_session(context)
      except BaseException as e:
        logging.debug(e)
        await context.close(1011, "Internal error")
      finally:
        if context.connected: await context.close()

  async def _ws_session(self, context: WebsocketContext):
    await context.accept()
    typ, message = await context.receive()
    if typ != "message" or message is None: raise ValueError("Invalid init message!")

    init_message = AppWebsocketInitMessage.model_validate_json(message)

    async with Session(self._get_session_config(True), self.content()) as session:
      await session.init(init_message.state_token)

      session.set_headers(context.headers)

      while True:
        typ, message = await context.receive()
        if typ != "message" or message is None: return

        update_message = AppWebsocketUpdateMessage.model_validate_json(message)
        session.set_location(update_message.location)
        await session.handle_events(update_message.events)
        await session.update()

        data = await session.render_update(include_state_token=init_message.enableStateUpdates, render_full=False)
        await context.send_message(data.model_dump_json())

  async def _http_session(self, context: HTTPContext):
    async with Session(self._get_session_config(False), self.content()) as session:
      location = context.path
      if context.query_string is not None: location += f"?{context.query_string}"

      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        await session.init(req.state_token)
        events = req.events
      else:
        session.set_location(location)
        await session.init(None)
        events = []


      session.set_location(location)
      session.set_headers(context.headers)

      await session.handle_events(events)
      await session.update()

      if context.method == "POST":
        result = await session.render_update(include_state_token=True, render_full=False)
        await context.respond_json_string(result.model_dump_json())
      else:
        result = await session.render_page()
        await context.respond_text(result, mime_type="text/html")

  async def _handle_http(self, context: HTTPContext):
    if context.path == "/rxxxt-client.js":
      with importlib.resources.path("rxxxt.assets", "main.js") as file_path:
        await context.respond_file(file_path)
    elif context.method in [ "GET", "POST" ]: await self._http_session(context)
    else: await context.respond_status(404)

  def _get_session_config(self, persistent: bool):
    return SessionConfig(page_facotry=self.page_layout, state_resolver=self.state_resolver, persistent=persistent)
