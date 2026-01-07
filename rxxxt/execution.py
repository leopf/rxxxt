import asyncio, hashlib, functools, re, dataclasses
from datetime import datetime
from pydantic import BaseModel
from typing import Any, Callable
from rxxxt.helpers import T, match_path
from rxxxt.state import State, StateConsumer

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]
OutputEvent = dict[str, Any]

class InputEventDescriptorOptions(BaseModel):
  debounce: int | None = None
  throttle: int | None = None
  no_trigger: bool = False
  prevent_default: bool = False
  param_map: dict[str, str] = dataclasses.field(default_factory=dict)
  default_params: dict[str, int | float | str | bool | None] | None = None

class InputEventDescriptor(BaseModel):
  context_id: str
  options: InputEventDescriptorOptions

class InputEvent(BaseModel):
  context_id: str
  data: dict[str, int | float | str | bool | None]

@dataclasses.dataclass
class Execution:
  output_events: list[OutputEvent]
  pending_updates: set[ContextStack]
  update_pending_event: asyncio.Event

  @property
  def is_websocket_closing(self):
    return any(event["event"] == "use-websocket" and event["websocket"] == False for event in self.output_events)

  def request_update(self, id: ContextStack):
    self.pending_updates.add(id)
    self.update_pending_event.set()

  def add_output_event(self, event: OutputEvent):
    self.output_events.append({ k: v for k, v in event.items() if v is not None })
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

@functools.lru_cache(maxsize=2048)
def get_context_stack_sid(stack: ContextStack):
  hasher = hashlib.sha256()
  for k in stack:
    if isinstance(k, str): k = k.replace(";", ";;")
    else: k = str(k)
    hasher.update((k + ";").encode("utf-8"))
  return hashlib.sha256(hasher.digest()).hexdigest() # NOTE: double hash to prevent hash continuation

@dataclasses.dataclass(frozen=True)
class ContextConfig:
  persistent: bool
  render_meta: bool

@dataclasses.dataclass(frozen=True)
class Context:
  id: ContextStack
  state: State
  registry: dict[str, Any]
  config: ContextConfig
  execution: Execution

  class StateConsumer(StateConsumer):
    def __init__(self, context: 'Context') -> None: self.context = context
    def consume(self, key: str, producer: Callable[[], str]) -> Any: self.context.request_update()
    def detach(self, key: str) -> Any: self.context.request_update()

  def __hash__(self) -> int:
    return hash(self.id)

  @functools.cached_property
  def update_consumer(self): return Context.StateConsumer(self)

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
  def subscribe(self, key: str): self.state.get(key).add_consumer(self.update_consumer)

  def emit(self, name: str, data: dict[str, int | float | str | bool | None]):
    self.execution.add_output_event(dict(event="custom", name=name, data=data))

  def navigate(self, location: str):
    is_full_url = ":" in location # colon means full url
    if not is_full_url: self.state.get("!location").set(location)
    self.execution.add_output_event(dict(event="navigate", location=location, requires_refresh=is_full_url or None))

  def use_websocket(self, websocket: bool = True): self.execution.add_output_event(dict(event="use-websocket", websocket=websocket))

  def set_cookie(self, name: str, value: str | None = None, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None, mirror_state: bool = True):
    if not re.match(r'^[^=;, \t\n\r\f\v]+$', name): raise ValueError("Invalid cookie name")
    if value is not None and not re.match(r'^[^;, \t\n\r\f\v]+$', value): raise ValueError("Invalid value.")
    if domain is not None and not re.match(r'^[^;, \t\n\r\f\v]+$', domain): raise ValueError("Invalid domain.")
    if path is not None and not re.match(r'^[^\x00-\x20;,\s]+$', path): raise ValueError("Invalid path.")

    expires_str = None if expires is None else expires.isoformat()

    self.execution.add_output_event(dict(event="set-cookie", name=name, value=value, expires=expires_str, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
    if mirror_state:
      self.state.set_many({ "!header;cookie": "; ".join(f"{k}={v}" for k, v in (self.cookies | { name: value }).items()) })

  def delete_cookie(self, name: str, mirror_state: bool = True):
    self.set_cookie(name=name, max_age=-1, mirror_state=False)
    if mirror_state:
      self.state.set_many({ "!header;cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items() if k != name) })

  def _get_state_str_subscribe(self, key: str):
    res = self.state.get(key).get()
    self.subscribe(key)
    return res
