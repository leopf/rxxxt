import asyncio
from dataclasses import dataclass
import json
from pydantic import BaseModel
from rxxxt.elements import El, Element, HTMLFragment, UnescapedHTMLElement, meta_element
from rxxxt.execution import Context, ContextConfig, InputEvent, OutputEvent, State
from rxxxt.helpers import to_awaitable
from rxxxt.page import PageFactory
from rxxxt.renderer import Renderer, render_node
from rxxxt.state import StateResolver

class InitOutputData(BaseModel):
  path: str
  state_token: str
  events: list[OutputEvent]

class UpdateOutputData(BaseModel):
  state_token: str | None = None
  events: list[OutputEvent]
  html_parts: list[str]

@dataclass
class SessionConfig:
  persistent: bool
  page_facotry: PageFactory
  state_resolver: StateResolver

  def get_context_config(self): return ContextConfig(persistent=self.persistent)

class Session:
  def __init__(self, config: SessionConfig, base: Element) -> None:
    self._update_event = asyncio.Event()
    self.config = config
    self.state = State(self._update_event)

    root_node = meta_element("root", base).tonode(Context(self.state, config.get_context_config(), ("root",)))
    self._root_renderer = Renderer(root_node)
    self._last_token: str | None = None

  async def __aenter__(self): return self
  async def __aexit__(self, *_): await self.destroy()

  async def wait_for_update(self): await self._update_event.wait()

  async def init(self, state_token: str | None):
    if state_token is not None:
      self._last_token = state_token
      state = await to_awaitable(self.config.state_resolver.resolve, state_token)
      for k, v in state.items(): self.state.set_state(k, v)

    await self._root_renderer.expand()

  async def destroy(self):
    await self._root_renderer.destroy()

  async def update(self):
    await self._root_renderer.update(self.state.pop_updates())

  async def handle_events(self, events: list[InputEvent]):
    await self._root_renderer.handle_events(events)

  def set_location(self, location: str): self.state.set_state("location", location)
  def set_headers(self, headers: dict[str, list[str]]): self.state.set_state("headers", json.dumps(headers))

  async def render_update(self, include_state_token: bool, render_full: bool):
    state_token: str | None = None
    if include_state_token: state_token = await self._update_state_token()

    html_parts = [self._root_renderer.render_full()] if render_full else self._root_renderer.render_partial()
    return UpdateOutputData(state_token=state_token, html_parts=html_parts, events=self.state.pop_output_events())

  async def render_page(self):
    init_data = InitOutputData(state_token=await self._update_state_token(), events=self.state.pop_output_events(), path="")

    content_el = UnescapedHTMLElement(self._root_renderer.render_full())
    header_el = HTMLFragment([ El.script(src="/rxxxt-client.js"), El.style(content=["rxxxt-meta { display: contents; }"]) ])
    body_end_el = HTMLFragment([ El.script(content=[ UnescapedHTMLElement(f"window.rxxxt.init({init_data.model_dump_json()});") ]) ])

    page = self.config.page_facotry(header_el, content_el, body_end_el)
    node = page.tonode(Context(self.state, ContextConfig(persistent=False), ("page",)))
    await node.expand()
    res = render_node(node)
    await node.destroy()
    return res

  async def _update_state_token(self):
    self._last_token = await to_awaitable(self.config.state_resolver.create_token, self.state.data, self._last_token)
    return self._last_token
