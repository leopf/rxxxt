import base64
from dataclasses import dataclass
from datetime import datetime
import functools
import hashlib
import re
from typing import Any, Literal
from pydantic import BaseModel, field_serializer, field_validator

from rxxxt.elements import Element
from rxxxt.helpers import to_awaitable
from rxxxt.state import StateBase, StateFactory


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

class UseWebsocketOutputEvent(BaseModel):
  event: Literal["use-websocket"] = "use-websocket"
  websocket: bool

class ForceRefreshOutputEvent(BaseModel):
  event: Literal["force-refresh"] = "force-refresh"

class NavigateOutputEvent(BaseModel):
  location: str
  event: Literal["navigate"] = "navigate"

ExecutionOutputEvent = SetCookieOutputEvent | NavigateOutputEvent | ForceRefreshOutputEvent | UseWebsocketOutputEvent

@dataclass
class ExecutionInput:
  events: list[ContextInputEvent]
  path: str
  params: dict[str, str]
  query_string: str | None

class AppExecutor:
  def __init__(self, raw_state: dict[str, str], headers: dict[str, list[str]], app_data: dict[str, Any]) -> None:
    self.app_data = app_data
    self.headers = headers
    self._raw_state = raw_state
    self._state: dict[str, StateBase] = {}

  @functools.cached_property
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

  async def execute_root(self, context_parts: list[str], element: 'Element', exec_input: ExecutionInput):
    context_id, execution = "", AppExecution(self, exec_input)
    for part in context_parts: context_id = execution.get_context_id(context_id, part)
    html_output = await element.to_html(Context(context_id, execution))
    return html_output, execution

  async def get_state(self, name: str, context: 'Context', state_factory: StateFactory):
    key = context.id + "!" + name
    if key in self._state:
      state = self._state[key]
    elif key in self._raw_state:
      raw_state = self._raw_state[key]
      state = state_factory(raw_state)
      self._state[key] = state
    else:
      state = self._state[key] = state_factory(None)
      await to_awaitable(state.init, context)
    return state

  def get_raw_state(self): return { k: v.to_json() for k, v in self._state.items() }

class AppExecution:
  def __init__(self, executor: AppExecutor, input_data: ExecutionInput) -> None:
    self.executor = executor
    self.execution_input = input_data
    self.output_events: list[ExecutionOutputEvent] = []
    self._context_parents: dict[str, str] = {}
    self._unique_ids: set[str] = set()

  def get_context_id(self, parent_id: str, suffix: str):
    counter = 0
    prefix = parent_id + ";" + suffix
    raw_ctx_id = prefix + "#" + str(counter)
    while raw_ctx_id in self._unique_ids:
      counter += 1
      raw_ctx_id = prefix + "#" + str(counter)
    self._unique_ids.add(raw_ctx_id)
    ctx_id = base64.urlsafe_b64encode(hashlib.sha1(raw_ctx_id.encode("utf-8")).digest()).decode("utf-8")
    self._context_parents[ctx_id] = parent_id
    return ctx_id

  def get_context_events(self, context_id: str): return (e for e in self.execution_input.events if e.context_id == context_id)

class Context:
  def __init__(self, id: str, execution: AppExecution) -> None:
    self.id = id
    self.execution = execution

  @property
  def query_string(self): return self.execution.execution_input.query_string

  @property
  def path(self): return self.execution.execution_input.path

  @property
  def params(self): return self.execution.execution_input.params

  @property
  def headers(self): return self.execution.executor.headers

  @property
  def app_data(self): return self.execution.executor.app_data

  def get_events(self): return self.execution.get_context_events(self.id)

  async def get_state(self, name: str, state_factory: StateFactory, is_global: bool = False):
    context = Context("", self.execution) if is_global else self
    return await self.execution.executor.get_state(name, context, state_factory)

  def navigate(self, location: str): self.execution.output_events.append(NavigateOutputEvent(location=location))
  def use_websocket(self, websocket: bool = True): self.execution.output_events.append(UseWebsocketOutputEvent(websocket=websocket))
  def get_cookie(self, name: str) -> str | None: return self.execution.executor.cookies.get(name, None)
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, max_age=-1))

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(id=self.execution.get_context_id(self.id, key), execution=self.execution)
