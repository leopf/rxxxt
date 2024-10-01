from dataclasses import dataclass
from datetime import datetime
import functools
import re
from typing import Literal
from pydantic import BaseModel, field_serializer, field_validator

from rxxxt.elements import Element
from rxxxt.state import State


def validate_key(key: str):
  if ";" in key: raise ValueError("Key must not contain a semicolon.")
  if "!" in key: raise ValueError("Key must not contain an exclamation mark.")
  if "#" in key: raise ValueError("Key must not contain a hashtag.")

class ContextInputEvent(BaseModel):
  context_id: str
  handler_name: str
  data: dict[str, int | float | str | bool]

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

class UpgradeWebsocketOutputEvent(BaseModel):
  event: Literal["upgrade-websocket"] = "upgrade-websocket"

class ForceRefreshOutputEvent(BaseModel):
  event: Literal["force-refresh"] = "force-refresh"

class NavigateOutputEvent(BaseModel):
  location: str
  event: Literal["navigate"] = "navigate"

ExecutionOutputEvent = SetCookieOutputEvent | NavigateOutputEvent | ForceRefreshOutputEvent | UpgradeWebsocketOutputEvent

@dataclass
class ExecutionInput:
  events: list[ContextInputEvent]
  path: str
  params: dict[str, str]
  query_string: str | None

class AppExecutor:
  def __init__(self, raw_state: dict[str, str], headers: dict[str, list[str]]) -> None:
    self._raw_state = raw_state
    self._headers = headers
    self._state: dict[str, State] = {}

  @functools.cached_property
  def cookies(self) -> dict[str, str]:
    values = self._headers.get("cookie", [])
    if len(values) == 0: return {}
    result: dict[str, str] = {}
    for cookie in values[0].split(";"):
      try:
        eq_idx = cookie.index("=")
        result[cookie[:eq_idx]] = cookie[(eq_idx + 1):]
      except ValueError: pass
    return result

  async def execute(self, context_prefix: str, element: 'Element', exec_input: ExecutionInput):
    execution = AppExecution(self, exec_input)
    html_output = await element.to_html(Context(context_prefix, execution))
    return html_output, execution.output_events

  def get_state(self, name: str, context: str, state_type: type[State]):
    key = context + "!" + name
    if key in self._state:
      state = self._state[key]
      if not isinstance(state, state_type): raise ValueError("Invalid state type for state!")
    elif key in self._raw_state:
      raw_state = self._raw_state[key]
      state = state_type.model_validate_json(raw_state)
      self._state[key] = state
    else:
      state = self._state[key] = state_type()
    return state

  def get_raw_state(self): return { k: v.model_dump_json() for k, v in self._state.items() }

class AppExecution:
  def __init__(self, executor: AppExecutor, input_data: ExecutionInput) -> None:
    self.executor = executor
    self.output_events: list[ExecutionOutputEvent] = []
    self._unique_ids: set[str] = set()
    self._input_events: dict[str, list[ContextInputEvent]] = { e.context_id: [] for e in input_data.events }
    for e in input_data.events:
      self._input_events[e.context_id].append(e)

  def get_context_id(self, prefix: str):
    counter = 0
    ctx_id = prefix + "#" + str(counter)
    while ctx_id in self._unique_ids:
      counter += 1
      ctx_id = prefix + "#" + str(counter)
    self._unique_ids.add(ctx_id)
    return ctx_id

  def pop_context_events(self, context_id: str): return self._input_events.pop(context_id, [])

class Context:
  def __init__(self, id: str, execution: AppExecution) -> None:
    self.id = id
    self.execution = execution

  def pop_events(self): return self.execution.pop_context_events(self.id)

  def get_state(self, name: str, state_type: type[State], is_global: bool = False):
    state_context_id = "" if is_global else self.id
    return self.execution.executor.get_state(name, state_context_id, state_type)

  def navigate(self, location: str): self.execution.output_events.append(NavigateOutputEvent(location=location))
  def upgrade_to_websocket(self): self.execution.output_events.append(UpgradeWebsocketOutputEvent())
  def get_cookie(self, name: str) -> str | None: return self.execution.executor.cookies.get(name, None)
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, max_age=-1))

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(id=self.execution.get_context_id(self.id + ";" + key), execution=self.execution)