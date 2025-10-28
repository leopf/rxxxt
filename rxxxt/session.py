import asyncio
from dataclasses import dataclass
from pydantic import BaseModel
from rxxxt.elements import El, Element, HTMLFragment, ScriptContent, UnescapedHTMLElement, meta_element
from rxxxt.execution import Context, ContextConfig, Execution, InputEvent, OutputEvent
from rxxxt.helpers import to_awaitable
from rxxxt.node import LazyNode
from rxxxt.page import PageFactory
from rxxxt.renderer import Renderer, render_node
from rxxxt.state import StateResolver, State

class InitOutputData(BaseModel):
  path: str
  state_token: str
  events: tuple[OutputEvent, ...]
  enable_web_socket_state_updates: bool | None = None
  disable_http_update_retry: bool | None = None

class UpdateOutputData(BaseModel):
  state_token: str | None = None
  events: tuple[OutputEvent, ...]
  html_parts: tuple[str, ...]

@dataclass
class AppConfig:
  enable_web_socket_state_updates: bool | None = None
  disable_http_update_retry: bool | None = None

@dataclass
class SessionConfig:
  persistent: bool
  page_facotry: PageFactory
  state_resolver: StateResolver
  app_config: AppConfig

class Session:
  def __init__(self, config: SessionConfig, base: Element) -> None:
    self._update_event = asyncio.Event()
    self.config = config
    self.state = State()
    self.execution = Execution(output_events=[], pending_updates=set(), update_pending_event=self._update_event)

    context_config = ContextConfig(persistent=config.persistent, render_meta=True)
    self._root_renderer = Renderer(LazyNode(Context(id=("root",), state=self.state, registry={}, config=context_config, execution=self.execution),
      meta_element("root", base).tonode))
    self._last_token: str | None = None

  @property
  def update_pending(self):
    return self._update_event.is_set()

  async def __aenter__(self): return self
  async def __aexit__(self, *_): await self.destroy()

  async def wait_for_update(self):
    self.execution.reset_event()
    while not self._update_event.is_set():
      _ = await self._update_event.wait()
      await asyncio.sleep(0.001)
      self.execution.reset_event()

  async def init(self, state_token: str | None):
    if state_token is not None:
      self._last_token = state_token
      user_data = await to_awaitable(self.config.state_resolver.resolve, state_token)
      self.state.set_many(user_data)

    await self._root_renderer.expand()

  async def destroy(self):
    await self._root_renderer.destroy()
    self.state.destroy()

  async def update(self, *, optional: bool = False):
    if optional and not self.update_pending: return
    await self._root_renderer.update(self.execution.pop_pending_updates())
    self.state.cleanup({ "#" })
    self.execution.reset_event()

  async def handle_events(self, events: tuple[InputEvent, ...]):
    await self._root_renderer.handle_events(events)

  def set_location(self, location: str): self.state.set_many({ "!location": location })
  def set_headers(self, headers: dict[str, tuple[str, ...]]):
    headers_kvs = { f"!header;{k}": "\n".join(v) for k, v in headers.items() }
    olds_header_keys = set(k for k in self.state.keys if k.startswith("!header;"))
    olds_header_keys.difference_update(headers_kvs.keys())
    for k in olds_header_keys: self.state.delete(k)
    self.state.set_many(headers_kvs)

  async def render_update(self, include_state_token: bool, render_full: bool):
    state_token: str | None = None
    if include_state_token: state_token = await self._update_state_token()

    html_parts: tuple[str, ...] = (self._root_renderer.render_full(),) if render_full else self._root_renderer.render_partial()
    return UpdateOutputData(state_token=state_token, html_parts=html_parts, events=self.execution.pop_output_events())

  async def render_page(self, path: str):
    init_data = InitOutputData(state_token=await self._update_state_token(), events=self.execution.pop_output_events(), path=path,
      disable_http_update_retry=self.config.app_config.disable_http_update_retry,
      enable_web_socket_state_updates=self.config.app_config.enable_web_socket_state_updates)

    content_el = UnescapedHTMLElement(self._root_renderer.render_full())
    header_el = El.style(content=["rxxxt-meta { display: contents; }"])
    body_end_el = HTMLFragment([
      El.script(type="application/json", id="rxxxt-init-data", content=[ ScriptContent(init_data.model_dump_json(exclude_defaults=True)) ]),
      El.script(src="/rxxxt-client.js")
    ])

    page = self.config.page_facotry(header_el, content_el, body_end_el)
    page_context_config = ContextConfig(persistent=False, render_meta=False)
    node = page.tonode(Context(id=("page",), state=self.state, registry={}, config=page_context_config, execution=self.execution))
    await node.expand()
    res = render_node(node)
    await node.destroy()
    return res

  async def _update_state_token(self):
    self.state.cleanup({ "#" })
    self._last_token = await to_awaitable(self.config.state_resolver.create_token, self.state.get_key_values({ "!", "#" }), self._last_token)
    return self._last_token
