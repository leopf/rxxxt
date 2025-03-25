import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
import functools
import hashlib
from typing import Literal
from pydantic import TypeAdapter
from rxxxt.events import ContextInputEventDescriptor, EventRegisterQuerySelectorEvent, NavigateOutputEvent, \
  OutputEvent, UseWebsocketOutputEvent, SetCookieOutputEvent, EventRegisterWindowEvent, ContextInputEventDescriptorGenerator

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]
HeaderValuesAdapter = TypeAdapter(list[str])

class State:
  """
  State keys may have prefixes. These prefixes inidcate how and when and if a key should be removed from the state.
  Prefixes:
    "#" = temporary - removed from the user data and session state, if no longer used
    "!" = protocol - removed from user state, if not used but not purged from the session
  """
  def __init__(self, update_event: asyncio.Event) -> None:
    self._state: dict[str, str] = {}
    self._state_subscribers: dict[str, set[ContextStack]] = {}
    self._pending_updates: set[ContextStack] = set()
    self._output_events: list[OutputEvent] = []
    self._update_event = update_event

  @property
  def user_data(self): return self._clean_state({ "#", "!" })

  @property
  def keys(self): return list(self._state.keys())

  def get_state(self, context_id: ContextStack, key: str) -> str | None:
    self._state_subscribers.setdefault(key, set()).add(context_id)
    return self._state.get(key)

  def set_state(self, key: str, value: str | None):
    if value != self._state.get(key, None):
      for cid in self._state_subscribers.get(key, []): self.request_update(cid)
      if value is None: self._state.pop(key, None)
      else: self._state[key] = value

  def state_exists(self, key: str): return key in self._state

  def cleanup(self): self._state = self._clean_state({ "#" })

  def add_output_event(self, event: OutputEvent): self._output_events.append(event)
  def pop_output_events(self):
    res = self._output_events
    self._output_events = []
    return res
  def pop_updates(self):
    res = self._pending_updates
    self._pending_updates = set()
    self._set_update_event()
    return res
  def request_update(self, cid: ContextStack):
    self._pending_updates.add(cid)
    self._set_update_event()

  def unregister(self, cid: ContextStack): # cleanup for lower memory usage
    if cid in self._pending_updates: self._pending_updates.remove(cid)
    self._set_update_event()

    for subs in self._state_subscribers.values():
      if cid in subs: subs.remove(cid)

  def _clean_state(self, prefixes: set[str]):
    used_keys = set(k for k, v in self._state_subscribers.items() if len(v) > 0)
    keep_keys = set(k for k in self._state.keys() if len(k) == 0 or k[0] not in prefixes) | used_keys
    return { k: v for k, v in self._state.items() if k in keep_keys }

  def _set_update_event(self):
    if len(self._pending_updates) > 0: self._update_event.set()
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
  def __init__(self, state: State, config: ContextConfig, stack: ContextStack) -> None:
    self._stack: ContextStack = stack
    self._state = state
    self._config = config

  @property
  def config(self): return self._config

  @property
  def id(self): return self._stack

  @cached_property
  def sid(self): return get_context_stack_sid(self._stack)

  @property
  def stack_sids(self):
    return [ get_context_stack_sid(self._stack[:i]) for i in range(1, len(self._stack)) ]

  @property
  def location(self):
    res = self._state.get_state(self._stack, "!location")
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

  def sub(self, key: ContextStackKey): return Context(self._state, self._config, self._stack + (key,))
  def replace_index(self, key: str):
    if isinstance(self._stack[-1], int): return Context(self._state, self._config, self._stack[:-1] + (key,))
    raise ValueError("No index to replace!")

  def set_state(self, key: str, value: str): self._state.set_state(key, value)
  def get_state(self, key: str): return self._state.get_state(self.id, key)
  def state_exists(self, key: str): return self._state.state_exists(key)
  def get_header(self, name: str) -> list[str]:
    header_json = self.get_state(f"!header;{name}")
    if header_json is None: return []
    else: return HeaderValuesAdapter.validate_json(header_json)

  def request_update(self): self._state.request_update(self._stack)
  def unregister(self): self._state.unregister(self._stack)

  def add_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "add")
  def add_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "add")

  def remove_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator):
    self._modify_window_event(name, descriptor, "remove")
  def remove_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool = False):
    self._modify_query_selector_event(selector, name, descriptor, all, "remove")

  def navigate(self, location: str):
    self.set_state("!location", location)
    self._state.add_output_event(NavigateOutputEvent(location=location))
  def use_websocket(self, websocket: bool = True): self._state.add_output_event(UseWebsocketOutputEvent(websocket=websocket))
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self._state.add_output_event(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self._state.add_output_event(SetCookieOutputEvent(name=name, max_age=-1))

  def _modify_window_event(self, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, ContextInputEventDescriptorGenerator) else descriptor
    self._state.add_output_event(EventRegisterWindowEvent(name=name, mode=mode, descriptor=descriptor))
  def _modify_query_selector_event(self, selector: str, name: str, descriptor: ContextInputEventDescriptor | ContextInputEventDescriptorGenerator, all: bool, mode: Literal["add"] | Literal["remove"]):
    descriptor = descriptor.descriptor if isinstance(descriptor, ContextInputEventDescriptorGenerator) else descriptor
    self._state.add_output_event(EventRegisterQuerySelectorEvent(
      name=name,
      mode=mode,
      selector=selector,
      all=all,
      descriptor=descriptor))
