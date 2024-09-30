import datetime
import importlib.resources
import logging
from typing import Any
from pydantic import BaseModel, TypeAdapter, ValidationError
import jwt

from razz.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext
from razz.elements import CustomAttribute as CustomAttribute, El, Element as Element, ElementFactory, HTMLFragment, UnescapedHTMLElement
from razz.execution import AppExecutor, ContextInputEvent, ExecutionInput, ExecutionOutputEvent, ForceRefreshOutputEvent
from razz.helpers import PathPattern
from razz.page import Page, PageFactory


class AppHttpRequest(BaseModel):
  stateToken: str
  events: list[ContextInputEvent]

class AppHttpResult(BaseModel):
  stateToken: str
  events: list[ExecutionOutputEvent]

class AppHttpPostResponse(AppHttpResult):
  html: str

RawStateAdapter = TypeAdapter(dict[str, str])

class App:
  def __init__(self, jwt_secret: bytes, session_duration: datetime.timedelta | None = None, jwt_algorithm: str = "HS512") -> None:
    self.page_layout: PageFactory = Page
    self._routes: list[tuple[PathPattern, ElementFactory]] = []
    self._session_duration = datetime.timedelta(hours=1) if session_duration is None else session_duration
    self._jwt_secret = jwt_secret
    if not jwt_algorithm.startswith("HS"): raise ValueError("JWT algorithm must start with HS")
    self._jwt_algorithm = jwt_algorithm

  def add_route(self, path: str, element_factory: ElementFactory): self._routes.append((PathPattern(path), element_factory))
  def route(self, path: str):
    def _inner(fn: ElementFactory):
      self.add_route(path, fn)
      return fn
    return _inner

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] == "http":
      context = HTTPContext(scope, receive, send)
      try: return await self._handle_http(context)
      except (ValidationError, ValueError) as e:
        logging.debug(e)
        return await context.respond_status(400)
      except BaseException as e:
        logging.debug(e)
        return await context.respond_status(500)

  async def _handle_http(self, context: HTTPContext):
    if context.path == "/razz-client.js":
      with importlib.resources.path("razz.assets", "main.js") as file_path:
        await context.respond_file(file_path)
    elif context.method in [ "GET", "POST" ] and (route := self._get_route(context.path)) is not None:
      params, element_factory = route
      def create_element(): return El["razz-meta"](id="razz-root", content=[element_factory()])

      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        state, events = self._verify_state(req.stateToken), req.events
      else: state, events={}, []

      executor = AppExecutor(state, context.headers)

      html_output, output_events = await executor.execute(create_element(), ExecutionInput(
        events=events,
        params=params,
        path=context.path,
        query_string=context.query_string
      ))

      # TODO: handle output events

      if len(events) > 0:
        if len(output_events) > 0: output_events.append(ForceRefreshOutputEvent())
        else:
          html_output, output_events = await executor.execute(create_element(), ExecutionInput(
            events=[],
            params=params,
            path=context.path,
            query_string=context.query_string
          ))

      state_token = self._sign_state(executor.get_raw_state())

      if context.method == "POST":
        await context.respond_json_string(AppHttpPostResponse(
          stateToken=state_token,
          events=output_events,
          html=html_output
        ).model_dump_json())
      else:
        header_el = HTMLFragment([
          El.script(src="/razz-client.js"),
          El.style(content=["razz-meta { display: contents; }"])
        ])
        body_end_el = HTMLFragment([
          El.script(content=[
            f"window.razzInit({AppHttpResult(stateToken=state_token, events=output_events).model_dump_json()});"
          ])
        ])
        content_el = UnescapedHTMLElement(html_output)
        page_html, _ = await executor.execute(self.page_layout(header_el, content_el, body_end_el), ExecutionInput(
          events=[],
          params=params,
          path=context.path,
          query_string=context.query_string
        ))
        await context.respond_text(page_html, mime_type="text/html")
    else: await context.respond_status(404)

  def _sign_state(self, state: dict[str, str]):
    return jwt.encode({ "data": state, "exp": datetime.datetime.now(tz=datetime.timezone.utc) + self._session_duration}, self._jwt_secret, self._jwt_algorithm)

  def _verify_state(self, token: str):
    token_data = jwt.decode(token, self._jwt_secret, algorithms=[self._jwt_algorithm])
    return RawStateAdapter.validate_python(token_data["data"])

  def _get_route(self, path: str):
    for pattern, element_factory in self._routes:
      if (match := pattern.match(path)) is not None:
        return match, element_factory
    return None
