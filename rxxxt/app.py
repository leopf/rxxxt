import importlib.resources
import logging
import os
import secrets
from typing import Any, Literal
from pydantic import BaseModel, TypeAdapter, ValidationError

from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext, WebsocketContext
from rxxxt.elements import CustomAttribute as CustomAttribute, El, Element, ElementFactory, HTMLFragment, UnescapedHTMLElement
from rxxxt.execution import AppExecution, AppExecutor, ContextInputEvent, ExecutionInput, ExecutionOutputEvent, ForceRefreshOutputEvent, Context
from rxxxt.helpers import PathPattern, to_awaitable
from rxxxt.page import Page, PageFactory
from rxxxt.state import JWTStateResolver, StateResolver, StateResolverError

class AppHttpRequest(BaseModel):
  stateToken: str
  events: list[ContextInputEvent]

class AppHttpResultBase(BaseModel):
  stateToken: str
  events: list[ExecutionOutputEvent]

class AppInitData(AppHttpResultBase):
  path: str

class AppHttpPostResponse(AppHttpResultBase):
  html_parts: list[str]

class AppWebsocketInitMessage(BaseModel):
  type: Literal["init"]
  stateToken: str
  enableStateUpdates: bool

class AppWebsocketUpdateMessage(BaseModel):
  type: Literal["update"]
  events: list[ContextInputEvent]
  location: str

  @property
  def path(self): return self.location.split("?")[0]

  @property
  def query_string(self):
    parts = self.location.split("?")
    return parts[1] if len(parts) > 1 else None

class AppWebsocketResponseMessage(BaseModel):
  stateToken: str | None = None
  events: list[ExecutionOutputEvent]
  html_parts: list[str]
  end: bool

RawStateAdapter = TypeAdapter(dict[str, str])

class Router(ElementFactory):
  class RoutedElement(Element):
    def __init__(self, routes: list[tuple[PathPattern, ElementFactory]]):
      self._routes = routes

    async def to_html(self, context: Context):
      element = self._get_element(context.path)
      return await element.to_html(context.sub(AppExecution.get_hashed_id(context.path)))

    def _get_element(self, path: str):
      for pattern, element_factory in self._routes:
        if pattern.match(path) is not None:
          return element_factory() # TODO: provide match as context
      return El.h1(content=["Not found!"])

  def __init__(self) -> None:
    self._routes: list[tuple[PathPattern, ElementFactory]] = []

  def add_route(self, path: str, element_factory: ElementFactory): self._routes.append((PathPattern(path), element_factory))
  def route(self, path: str):
    def _inner(fn: ElementFactory):
      self.add_route(path, fn)
      return fn
    return _inner

  def __call__(self) -> Element: return Router.RoutedElement(self._routes)

class App:
  def __init__(self, content: ElementFactory, state_resolver: StateResolver | None = None, page_layout: PageFactory | None = None, app_data: dict[str, Any] = {}) -> None:
    self.content = content
    self.page_layout: PageFactory = page_layout or Page
    self.app_data = app_data
    if state_resolver is None:
      jwt_secret = os.getenv("JWT_SECRET", None)
      if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
      else: jwt_secret = jwt_secret.encode("utf-8")
      self.state_resolver: StateResolver = JWTStateResolver(jwt_secret)
    else: self.state_resolver = state_resolver

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] == "http":
      context = HTTPContext(scope, receive, send)
      try: await self._handle_http(context)
      except (ValidationError, ValueError) as e:
        logging.debug(e)
        return await context.respond_status(400)
      except BaseException as e:
        logging.debug(e)
        return await context.respond_status(500)
    elif scope["type"] == "websocket":
      context = WebsocketContext(scope, receive, send)
      try: await self._handle_websocket(context)
      except BaseException as e:
        logging.debug(e)
        await context.close(1011, "Internal error")
      finally:
        if context.connected: await context.close()

  async def _handle_websocket(self, context: WebsocketContext):
    closing = False
    await context.accept()
    typ, message = await context.receive()
    if typ != "message" or message is None: raise ValueError("Invalid init message!")

    init_message = AppWebsocketInitMessage.model_validate_json(message)
    last_state_token = init_message.stateToken
    executor = AppExecutor(await self._get_state_from_token(last_state_token), context.headers)

    while not closing:
      typ, message = await context.receive()
      if typ == "disconnect" or typ == "connect": return

      update_message = AppWebsocketUpdateMessage.model_validate_json(message)

      html_output, execution = await executor.execute_root("content", self._render_content(), ExecutionInput(
        events=update_message.events,
        path=update_message.path,
        query_string=update_message.query_string
      ))

      output_events: list[ExecutionOutputEvent] = []
      for event in execution.output_events:
        if event.event == "use-websocket":
          if not event.websocket: closing = True
        else: output_events.append(event)

      if len(update_message.events) > 0:
        if len(output_events) > 0: output_events.append(ForceRefreshOutputEvent())
        else:
          html_output, execution = await executor.execute_root("content", self._render_content(), ExecutionInput(
            events=[],
            path=context.path,
            query_string=context.query_string
          ))
          output_events = execution.output_events

      state_token: str | None = None
      if init_message.enableStateUpdates or closing:
        state_token = await self._create_state_token(executor.get_raw_state(), last_state_token)
        last_state_token = state_token

      await context.send_message(AppWebsocketResponseMessage(
        events=output_events,
        html_parts=[html_output],
        stateToken=state_token,
        end=True
      ).model_dump_json())

  async def _handle_http(self, context: HTTPContext):
    if context.path == "/rxxxt-client.js":
      with importlib.resources.path("rxxxt.assets", "main.js") as file_path:
        await context.respond_file(file_path)
    elif context.method in [ "GET", "POST" ]:
      old_state_token: str | None = None
      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        old_state_token = req.stateToken
        state, events = await self._get_state_from_token(req.stateToken), req.events
      else: state, events={}, []

      executor = AppExecutor(state, context.headers)
      html_output, execution = await executor.execute_root("content", self._render_content(), ExecutionInput(
        events=events,
        path=context.path,
        query_string=context.query_string
      ))

      output_events: list[ExecutionOutputEvent] = []
      for event in execution.output_events:
        if event.event == "set-cookie": context.add_response_headers([(b"Set-Cookie", event.to_set_cookie_header().encode("utf-8"))])
        elif event.event == "use-websocket" and not event.websocket: pass
        else: output_events.append(event)

      if len(events) > 0:
        if len(output_events) > 0: output_events.append(ForceRefreshOutputEvent())
        else:
          html_output, execution = await executor.execute_root("content", self._render_content(), ExecutionInput(
            events=[],
            path=context.path,
            query_string=context.query_string
          ))
          output_events = execution.output_events

      state_token = await self._create_state_token(executor.get_raw_state(), old_state_token)

      if context.method == "POST":
        await context.respond_json_string(AppHttpPostResponse(
          stateToken=state_token,
          events=output_events,
          html_parts=[html_output]
        ).model_dump_json())
      else:
        header_el = HTMLFragment([ El.script(src="/rxxxt-client.js"), El.style(content=["rxxxt-meta { display: contents; }"]) ])
        body_end_el = HTMLFragment([ El.script(content=[ f"window.rxxxt.init({AppInitData(stateToken=state_token, events=output_events, path=context.path).model_dump_json()});" ]) ])
        content_el = UnescapedHTMLElement(html_output)
        page_html, _ = await executor.execute_root("page", self.page_layout(header_el, content_el, body_end_el), ExecutionInput(
          events=[],
          path=context.path,
          query_string=context.query_string
        ))
        await context.respond_text(page_html, mime_type="text/html")
    else: await context.respond_status(404)

  def _render_content(self): return El["rxxxt-meta"](id="rxxxt-root", content=[self.content()])

  async def _create_state_token(self, state: dict[str, str], old_token: str | None):
    return await to_awaitable(self.state_resolver.create_token, state, old_token)

  async def _get_state_from_token(self, token: str) -> dict[str, str]:
    try: return RawStateAdapter.validate_python(await to_awaitable(self.state_resolver.resolve, token))
    except StateResolverError: return {}
