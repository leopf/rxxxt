import hashlib
import importlib.resources
import logging
import os
import secrets
from typing import Any
from pydantic import BaseModel, TypeAdapter, ValidationError

from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext
from rxxxt.elements import CustomAttribute as CustomAttribute, El, Element as Element, ElementFactory, HTMLFragment, UnescapedHTMLElement
from rxxxt.execution import AppExecutor, ContextInputEvent, ExecutionInput, ExecutionOutputEvent, ForceRefreshOutputEvent
from rxxxt.helpers import PathPattern, to_awaitable
from rxxxt.page import Page, PageFactory
from rxxxt.state import JWTStateResolver, StateResolver, StateResolverError


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
  def __init__(self, state_resolver: StateResolver | None = None) -> None:
    self.page_layout: PageFactory = Page
    if state_resolver is None:
      jwt_secret = os.getenv("JWT_SECRET", None)
      if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
      else: jwt_secret = jwt_secret.encode("utf-8")
      self.state_resolver: StateResolver = JWTStateResolver(jwt_secret)
    else: self.state_resolver = state_resolver
    self._routes: list[tuple[PathPattern, ElementFactory]] = []

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
    if context.path == "/rxxxt-client.js":
      with importlib.resources.path("rxxxt.assets", "main.js") as file_path:
        await context.respond_file(file_path)
    elif context.method in [ "GET", "POST" ] and (route := self._get_route(context.path)) is not None:
      params, element_factory = route
      def create_element(): return El["rxxxt-meta"](id="rxxxt-root", content=[element_factory()])

      old_state_token: str | None = None
      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        old_state_token = req.stateToken
        state, events = await self._get_state_from_token(req.stateToken), req.events
      else: state, events={}, []

      executor = AppExecutor(state, context.headers)
      path_hash = hashlib.sha1(context.path.encode("utf-8")).hexdigest()
      content_ctx_prefix = path_hash + ";content"

      html_output, output_events = await executor.execute(content_ctx_prefix, create_element(), ExecutionInput(
        events=events,
        params=params,
        path=context.path,
        query_string=context.query_string
      ))

      noutput_events: list[ExecutionOutputEvent] = []
      for event in output_events:
        if event.event == "set-cookie": context.add_response_headers([(b"Set-Cookie", event.to_set_cookie_header().encode("utf-8"))])
        else: noutput_events.append(event)
      output_events = noutput_events

      # TODO: handle output events

      if len(events) > 0:
        if len(output_events) > 0: output_events.append(ForceRefreshOutputEvent())
        else:
          html_output, output_events = await executor.execute(content_ctx_prefix, create_element(), ExecutionInput(
            events=[],
            params=params,
            path=context.path,
            query_string=context.query_string
          ))

      state_token = await self._create_state_token(executor.get_raw_state(), old_state_token)

      if context.method == "POST":
        await context.respond_json_string(AppHttpPostResponse(
          stateToken=state_token,
          events=output_events,
          html=html_output
        ).model_dump_json())
      else:
        header_el = HTMLFragment([
          El.script(src="/rxxxt-client.js"),
          El.style(content=["rxxxt-meta { display: contents; }"])
        ])
        body_end_el = HTMLFragment([
          El.script(content=[
            f"window.rxxxtInit({AppHttpResult(stateToken=state_token, events=output_events).model_dump_json()});"
          ])
        ])
        content_el = UnescapedHTMLElement(html_output)
        page_html, _ = await executor.execute(path_hash + ";page", self.page_layout(header_el, content_el, body_end_el), ExecutionInput(
          events=[],
          params=params,
          path=context.path,
          query_string=context.query_string
        ))
        await context.respond_text(page_html, mime_type="text/html")
    else: await context.respond_status(404)

  async def _create_state_token(self, state: dict[str, str], old_token: str | None):
    return await to_awaitable(self.state_resolver.create_token, state, old_token)

  async def _get_state_from_token(self, token: str) -> dict[str, str]:
    try: return RawStateAdapter.validate_python(await to_awaitable(self.state_resolver.resolve, token))
    except StateResolverError: return {}

  def _get_route(self, path: str):
    for pattern, element_factory in self._routes:
      if (match := pattern.match(path)) is not None:
        return match, element_factory
    return None
