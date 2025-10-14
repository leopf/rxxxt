import asyncio, hashlib, functools, re, dataclasses
from datetime import datetime
from typing import Callable, Literal, Any
import weakref
from rxxxt.events import InputEventDescriptor, CustomOutputEvent, EventRegisterQuerySelectorEvent, NavigateOutputEvent, \
  OutputEvent, UseWebsocketOutputEvent, SetCookieOutputEvent, EventRegisterWindowEvent, InputEventDescriptorGenerator
from rxxxt.helpers import T, match_path
from rxxxt.newstate import State as NState, StateConsumer

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]

@functools.lru_cache(maxsize=2048)
def get_context_stack_sid(stack: ContextStack):
  hasher = hashlib.sha256()
  for k in stack:
    if isinstance(k, str): k = k.replace(";", ";;")
    else: k = str(k)
    hasher.update((k + ";").encode("utf-8"))
  return hashlib.sha256(hasher.digest()).hexdigest() # NOTE: double hash to prevent hash continuation

@dataclasses.dataclass
class Execution:
  output_events: list[OutputEvent]
  pending_updates: set[ContextStack]
  update_pending_event: asyncio.Event

  def request_update(self, id: ContextStack):
    self.pending_updates.add(id)
    self.update_pending_event.set()

  def add_output_event(self, event: OutputEvent):
    self.output_events.append(event)
    self.update_pending_event.set()

  def pop_output_events(self):
    res: list[OutputEvent] = []
    for event in self.output_events:
      if event not in res:
        res.append(event)
    self.output_events.clear()
    return tuple(res)

  def pop_pending_updates(self):
    result = set(self.pending_updates)
    self.pending_updates.clear()
    return result

  def reset_event(self):
    if len(self.pending_updates) == 0 and len(self.output_events) == 0:
      self.update_pending_event.clear()
    else:
      self.update_pending_event.set()

@dataclasses.dataclass(frozen=True)
class ContextConfig:
  persistent: bool
  render_meta: bool

@dataclasses.dataclass(frozen=True)
class Context:
  id: ContextStack
  state: NState
  registry: dict[str, Any]
  config: ContextConfig
  execution: Execution

  class StateConsumer(StateConsumer):
    _context_cache: weakref.WeakKeyDictionary['Context', 'Context.StateConsumer'] = weakref.WeakKeyDictionary()

    def __init__(self, context: 'Context') -> None: self.context = context
    def consume(self, key: str, producer: Callable[[], str]) -> Any: self.context.request_update()
    def detach(self, key: str) -> Any: self.context.request_update()

    @staticmethod
    def for_context(context: 'Context'):
      if (consumer := Context.StateConsumer._context_cache.get(context)) is None:
        consumer = Context.StateConsumer(context)
        Context.StateConsumer._context_cache[context] = consumer
      return consumer

  def __hash__(self) -> int:
    return id(self)

  @functools.cached_property
  def sid(self): return get_context_stack_sid(self.id)

  @property
  def stack_sids(self):
    return [ get_context_stack_sid(self.id[:i + 1]) for i in range(len(self.id)) ]

  @property
  def location(self):
    res = self._get_state_str_subscribe("!location")
    if res is None: raise ValueError("No location!")
    else: return res

  @property
  def path(self): return self.location.split("?")[0]

  @property
  def query_string(self):
    parts = self.location.split("?")
    if len(parts) < 2: return None
    else: return parts[1]

  @property
  def cookies(self) -> dict[str, str]:
    values = self.get_header("cookie")
    if len(values) == 0: return {}
    result: dict[str, str] = {}
    for cookie in values[0].split(";"):
      try:
        eq_idx = cookie.index("=")
        result[cookie[:eq_idx].strip()] = cookie[(eq_idx + 1):].strip()
      except ValueError: pass
    return result

  def sub(self, key: ContextStackKey): return dataclasses.replace(self, id=self.id + (key,))
  def replace_index(self, key: str):
    if isinstance(self.id[-1], int): return dataclasses.replace(self, id=self.id[:-1] + (key,))
    raise ValueError("No index to replace!")
  def update_registry(self, registry: dict[str, Any]): return dataclasses.replace(self, registry=self.registry | registry)
  def registered(self, name: str, t: type[T]) -> T:
    if not isinstance((val:=self.registry.get(name)), t):
      raise TypeError(f"Invalid type in get_registered '{type(val)}'!")
    return val

  def match_path(self, pattern: str, re_flags: int = re.IGNORECASE):
    return match_path(pattern, self.path, re_flags)

  def get_header(self, name: str) -> tuple[str, ...]:
    header_lines = self._get_state_str_subscribe(f"!header;{name}")
    if header_lines is None: return ()
    else: return tuple(header_lines.splitlines())

  def request_update(self): self.execution.request_update(self.id)
  def subscribe(self, key: str): self.state.get(key).add_consumer(Context.StateConsumer.for_context(self))

  def emit(self, name: str, data: dict[str, int | float | str | bool | None]):
    self.execution.add_output_event(CustomOutputEvent(name=name, data=data))

  def add_window_event(self, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "add")
  def add_query_selector_event(self, selector: str, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "add")

  def remove_window_event(self, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "remove")
  def remove_query_selector_event(self, selector: str, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "remove")

  def navigate(self, location: str):
    is_full_url = ":" in location # colon means full url
    if not is_full_url: self.state.get("!location").set(location)
    self.execution.add_output_event(NavigateOutputEvent(location=location, requires_refresh=is_full_url))
  def use_websocket(self, websocket: bool = True): self.execution.add_output_event(UseWebsocketOutputEvent(websocket=websocket))
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None, mirror_state: bool = True):
    self.execution.add_output_event(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
    if mirror_state:
      self.state.set_many({ "!header;cookie": "; ".join(f"{k}={v}" for k, v in (self.cookies | { name: value }).items()) })
  def delete_cookie(self, name: str, mirror_state: bool = True):
    self.execution.add_output_event(SetCookieOutputEvent(name=name, max_age=-1))
    if mirror_state:
      self.state.set_many({ "!header;cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items() if k != name) })
  def _get_state_str_subscribe(self, key: str):
    res = self.state.get(key).get()
    self.subscribe(key)
    return res
  def _modify_window_event(self, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, InputEventDescriptorGenerator) else descriptor
    self.execution.add_output_event(EventRegisterWindowEvent(name=name, mode=mode, descriptor=descriptor))
  def _modify_query_selector_event(self, selector: str, name: str, descriptor: InputEventDescriptor | InputEventDescriptorGenerator, all: bool, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, InputEventDescriptorGenerator) else descriptor
    self.execution.add_output_event(EventRegisterQuerySelectorEvent(name=name, mode=mode, selector=selector, all=all, descriptor=descriptor))
