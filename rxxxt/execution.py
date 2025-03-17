import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, TypeAdapter, field_serializer, field_validator

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]

class SetCookieOutputEvent(BaseModel):
  event: Literal["set-cookie"] = "set-cookie"
  name: str
  value: str | None = None
  expires: datetime | None = None
  path: str | None = None
  max_age: int | None = None
  secure: bool | None = None
  http_only: bool | None = None
  domain: str | None = None

  @field_validator('name')
  @classmethod
  def validate_name(cls, value: str):
    if not re.match(r'^[^=;, \t\n\r\f\v]+$', value): raise ValueError("Invalid cookie name")
    return value

  @field_validator('value', "domain")
  @classmethod
  def validate_value(cls, value: str | None):
    if value is None: return None
    if not re.match(r'^[^;, \t\n\r\f\v]+$', value): raise ValueError("Invalid value.")
    return value

  @field_validator('path')
  @classmethod
  def validate_path(cls, value: str | None):
    if value is None: return None
    if not re.match(r'^[^\x00-\x20;,\s]+$', value): raise ValueError("Invalid path value")
    return value

  @field_serializer('expires', when_used='json')
  def seriliaze_expires(self, value: datetime | None): return None if value is None else value.isoformat()

  def to_set_cookie_header(self):
    parts: list[str] = [f"{self.name}={self.value}"]
    if self.path is not None: parts.append(f"path={self.path}")
    if self.expires is not None: parts.append(f"expires={self.expires.strftime("%a, %d %b %G %T %Z")}")
    if self.max_age is not None: parts.append(f"max-age={self.max_age}")
    if self.domain is not None: parts.append(f"domain={self.domain}")
    if self.secure: parts.append("secure")
    if self.http_only: parts.append("httponly")
    return ";".join(parts)

class UseWebsocketOutputEvent(BaseModel):
  event: Literal["use-websocket"] = "use-websocket"
  websocket: bool

class NavigateOutputEvent(BaseModel):
  location: str
  event: Literal["navigate"] = "navigate"

class ContextInputEvent(BaseModel):
  context_id: str
  data: dict[str, int | float | str | bool]

InputEvent = ContextInputEvent
OutputEvent = SetCookieOutputEvent | NavigateOutputEvent | UseWebsocketOutputEvent
HeaderTypeAdapter = TypeAdapter(dict[str, list[str]])

class State:
  def __init__(self, update_event: asyncio.Event) -> None:
    self._state: dict[str, str] = {}
    self._state_subscribers: dict[str, set[ContextStack]] = {}
    self._pending_updates: set[ContextStack] = set()
    self._output_events: list[OutputEvent] = []
    self._update_event = update_event

  @property
  def data(self): return dict(self._state)

  def get_state(self, context_id: ContextStack, key: str) -> str | None:
    self._state_subscribers.setdefault(key, set()).add(context_id)
    return self._state.get(key)

  def set_state(self, key: str, value: str | None):
    if value != self._state.get(key, None):
      for cid in self._state_subscribers.get(key, []): self.request_update(cid)
      if value is None: self._state.pop(key, None)
      else: self._state[key] = value

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

  def _set_update_event(self):
    if len(self._pending_updates) > 0: self._update_event.set()
    else: self._update_event.clear()

@dataclass(frozen=True)
class ContextConfig:
  persistent: bool

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
  def sid(self):
    hasher = hashlib.sha256()
    for k in self._stack:
      if isinstance(k, str): k = k.replace(";", ";;")
      else: k = str(k)
      hasher.update((k + ";").encode("utf-8"))
    return hasher.hexdigest()

  @property
  def location(self):
    res = self._state.get_state(self._stack, "location")
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
  def headers(self): return HeaderTypeAdapter.validate_json(self.get_state("headers") or "")

  @property
  def cookies(self) -> dict[str, str]:
    values = self.headers.get("cookie", [])
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

  def request_update(self): self._state.request_update(self._stack)
  def unregister(self): self._state.unregister(self._stack)

  def navigate(self, location: str):
    self.set_state("location", location)
    self._state.add_output_event(NavigateOutputEvent(location=location))
  def use_websocket(self, websocket: bool = True): self._state.add_output_event(UseWebsocketOutputEvent(websocket=websocket))
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self._state.add_output_event(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self._state.add_output_event(SetCookieOutputEvent(name=name, max_age=-1))
