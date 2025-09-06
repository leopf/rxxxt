import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
import functools
import hashlib
import itertools
from typing import Literal, Any
from pydantic import TypeAdapter
from rxxxt.cell import StateCell, StrStateCell
from rxxxt.events import ContextInputEventDescriptor, EventRegisterQuerySelectorEvent, NavigateOutputEvent, \
  OutputEvent, UseWebsocketOutputEvent, SetCookieOutputEvent, EventRegisterWindowEvent, ContextInputEventDescriptorGenerator
from rxxxt.helpers import T

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]
HeaderValuesAdapter = TypeAdapter(tuple[str, ...])

class State:
  """
  State keys may have prefixes. These prefixes inidcate how and when and if a key should be removed from the state.
  Prefixes:
    "#" = temporary - removed from the user data and session state, if no longer used
    "!" = protocol - removed from user state, if not used but not purged from the session
  """

  def __init__(self, update_event: asyncio.Event) -> None:
    self._key_str_store: dict[str, str] = {}
    self._key_cell_store: dict[str, StateCell] = {}

    self._key_subscribers: dict[str, set[ContextStack]] = {}
    self._pending_updates: set[ContextStack] = set()
    self._output_events: list[OutputEvent] = []
    self._update_event = update_event

  @property
  def user_data(self):
    active_keys = self._get_active_keys({ "!", "#" })
    data = { k: v for k, v in self._key_str_store.items() if k in active_keys }
    data.update({ k: cell.serlialize() for k, cell in self._key_cell_store.items() if k in active_keys })
    return data

  @property
  def keys(self) -> set[str]: return set(itertools.chain(self._key_str_store.keys(), self._key_cell_store.keys()))

  def init(self, k_str_store: dict[str, str]): self._key_str_store.update(k_str_store)

  def get_key_str(self, key: str):
    if (v := self._key_str_store.get(key)) is None:
      cell = self._key_cell_store.get(key)
      if cell is not None: v = cell.serlialize()
    return v
  def get_key_cell(self, key: str): return self._key_cell_store.get(key)
  def set_key_cell(self, key: str, cell: StateCell, overwrite: bool = False):
    if key in self._key_cell_store and not overwrite:
      raise ValueError(f"Cell already registered with key '{key}'!")
    self._key_cell_store[key] = cell
  def delete_key(self, key: str):
    _ = self._key_str_store.pop(key, None)
    if (cell := self._key_cell_store.pop(key, None)) is not None:
      cell.destroy()

  def update_state_strs(self, data: dict[str, str]):
    for k, v in data.items():
      cell = self.get_key_cell(k)
      if cell is None:
        self.set_key_cell(k, StrStateCell(v))
      elif isinstance(cell, StrStateCell):
        cell.value = v
      else:
        raise ValueError("invalid cell for location!")
    self.request_key_updates(set(data.keys()))

  def request_context_updates(self, ids: set[ContextStack]):
    for id in ids: self._pending_updates.add(id)
    self._set_update_event()

  def request_key_updates(self, keys: set[str]):
    ids: set[ContextStack] = set(itertools.chain(*(self._key_subscribers.get(key, ()) for key in keys)))
    self.request_context_updates(ids)

  def subscribe(self, cid: ContextStack, key: str):
    self._key_subscribers.setdefault(key, set()).add(cid)

  def unsubscribe(self, cid: ContextStack, key: str):
    subs = self._key_subscribers.get(key)
    if subs is not None and cid in subs: subs.remove(cid)

  def unsubscribe_all(self, cid: ContextStack):
    if cid in self._pending_updates: self._pending_updates.remove(cid)
    for ids in self._key_subscribers.values():
      if cid in ids: ids.remove(cid)
    self._set_update_event()

  def add_output_event(self, event: OutputEvent):
    self._output_events.append(event)
    self._set_update_event()

  def pop_output_events(self):
    res = tuple(self._output_events)
    self._output_events = []
    return res

  def pop_updates(self):
    res = self._pending_updates
    self._pending_updates = set()
    self._set_update_event()
    return res

  def destroy(self):
    for cell in self._key_cell_store.values():
      cell.destroy()
    self._key_cell_store.clear()

  def cleanup(self):
    active_keys = self._get_active_keys({ "#" })
    self._key_str_store = { k: v for k, v in self._key_str_store.items() if k in active_keys }
    inactive_cells = set(self._key_cell_store.keys())
    inactive_cells.difference_update(active_keys)
    for k in inactive_cells:
      if (cell := self._key_cell_store.pop(k, None)) is not None:
        cell.destroy()
    self._key_subscribers = { k: v for k, v in self._key_subscribers.items() if len(v) > 0 }

  def _get_active_keys(self, inactive_prefixes: set[str]):
    active_keys = set(k for k, v in self._key_subscribers.items() if len(v) > 0)
    active_keys.update(k for k in self._key_str_store.keys() if len(k) == 0 or k[0] not in inactive_prefixes)
    active_keys.update(k for k in self._key_cell_store.keys() if len(k) == 0 or k[0] not in inactive_prefixes)
    return active_keys

  def _set_update_event(self):
    if len(self._pending_updates) > 0 or len(self._output_events) > 0: self._update_event.set()
    else: self._update_event.clear()

@functools.lru_cache(maxsize=256)
def get_context_stack_sid(stack: ContextStack):
  hasher = hashlib.sha256()
  for k in stack:
    if isinstance(k, str): k = k.replace(";", ";;")
    else: k = str(k)
    hasher.update((k + ";").encode("utf-8"))
  return hasher.hexdigest()

@dataclass(frozen=True)
class ContextConfig:
  persistent: bool
  render_meta: bool

class Context:
  def __init__(self, state: State, registry: dict[str, Any], config: ContextConfig, stack: ContextStack) -> None:
    self._stack: ContextStack = stack
    self._config = config
    self._registry: dict[str, Any] = dict(registry)
    self.state = state

  @property
  def config(self): return self._config

  @property
  def id(self): return self._stack

  @cached_property
  def sid(self): return get_context_stack_sid(self._stack)

  @property
  def stack_sids(self):
    return [ get_context_stack_sid(self._stack[:i + 1]) for i in range(len(self._stack)) ]

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
        result[cookie[:eq_idx]] = cookie[(eq_idx + 1):]
      except ValueError: pass
    return result

  def sub(self, key: ContextStackKey): return Context(self.state, self._registry, self._config, self._stack + (key,))
  def replace_index(self, key: str):
    if isinstance(self._stack[-1], int): return Context(self.state, self._registry, self._config, self._stack[:-1] + (key,))
    if isinstance(self._stack[-1], int): return Context(self.state, self._registry, self._config, self._stack[:-1] + (key,))
    raise ValueError("No index to replace!")
  def update_registry(self, registry: dict[str, Any]): return Context(self.state, self._registry | registry, self._config, self._stack)
  def registered(self, name: str, t: type[T]) -> T:
    if not isinstance((val:=self._registry.get(name)), t):
      raise TypeError(f"Invalid type in get_registered '{type(val)}'!")
    return val

  def get_header(self, name: str) -> tuple[str, ...]:
    header_lines = self._get_state_str_subscribe(f"!header;{name}")
    if header_lines is None: return ()
    else: return tuple(header_lines.splitlines())

  def request_update(self): self.state.request_context_updates({ self.id })
  def subscribe(self, key: str): self.state.subscribe(self.id, key)
  def unsubscribe(self, key: str): self.state.unsubscribe(self.id, key)
  def unsubscribe_all(self): self.state.unsubscribe_all(self.id)

  def add_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "add")
  def add_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "add")

  def remove_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "remove")
  def remove_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "remove")

  def navigate(self, location: str):
    self.state.update_state_strs({"!location": location})
    self.state.add_output_event(NavigateOutputEvent(location=location))
  def use_websocket(self, websocket: bool = True): self.state.add_output_event(UseWebsocketOutputEvent(websocket=websocket))
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self.state.add_output_event(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self.state.add_output_event(SetCookieOutputEvent(name=name, max_age=-1))

  def _get_state_str_subscribe(self, key: str):
    res = self.state.get_key_str(key)
    self.state.subscribe(self.id, key)
    return res
  def _modify_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, ContextInputEventDescriptorGenerator) else descriptor
    self.state.add_output_event(EventRegisterWindowEvent(name=name, mode=mode, descriptor=descriptor))
  def _modify_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, ContextInputEventDescriptorGenerator) else descriptor
    self.state.add_output_event(EventRegisterQuerySelectorEvent(
      name=name,
      mode=mode,
      selector=selector,
      all=all,
      descriptor=descriptor))
