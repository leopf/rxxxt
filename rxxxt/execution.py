import base64
from dataclasses import dataclass
from datetime import datetime
import functools
import hashlib
import re
import asyncio
from typing import Literal
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
  query_string: str | None

class AppExecutor:
  def __init__(self, raw_state: dict[str, str], headers: dict[str, list[str]]) -> None:
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

  async def execute_root(self, root_key: str, element: 'Element', exec_input: ExecutionInput):
    execution = AppExecution(self, exec_input)
    return await element.to_html(Context("", execution).sub(root_key)), execution

  async def execute_partial(self, execution: 'AppExecution'):
    context_ids = set(event.context_id for event in execution.execution_input.events) # TODO handle changed states as well
    roots = execution.prepare_roots(context_ids)
    return await asyncio.gather(*(root.to_html(Context(context_id, execution)) for context_id, root in roots))

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

    self.state_users: dict[StateBase, list[str]] = {}

    self.context_elements: dict[str, Element] = {}
    self._context_parents: dict[str, str] = {}
    self._unique_ids: set[str] = set()

  def get_context_id(self, parent_id: str, suffix: str):
    ctx_id = AppExecution.get_hashed_id(parent_id + ";" + suffix)
    while ctx_id in self._unique_ids: ctx_id = AppExecution.get_hashed_id(ctx_id + "#")
    self._unique_ids.add(ctx_id)
    self._context_parents[ctx_id] = parent_id
    return ctx_id

  def get_context_events(self, context_id: str): return (e for e in self.execution_input.events if e.context_id == context_id)

  def prepare_roots(self, context_ids: set[str]):
    root_ids = self._get_context_roots(context_ids)
    context_children = self._get_context_children(root_ids)

    for child_id in context_children:
      self._context_parents.pop(child_id, None)
      self.context_elements.pop(child_id, None)

    self._unique_ids.difference_update(context_children)
    self.state_users = { state: [u for u in users if u not in context_children] for state, users in self.state_users.items() }
    return [ (root_id, self.context_elements[root_id]) for root_id in root_ids ] # NOTE: all roots should be tracked

  def _get_context_roots(self, context_ids: set[str]):
    return set(context_id for context_id in context_ids if all(parent not in context_ids for parent in self._get_context_parents(context_id)))

  def _get_context_children(self, context_ids: set[str]):
      context_children: dict[str, list[str]] = {}
      for c, p in self._context_parents: context_children.setdefault(p, []).append(c)
      total = set(context_ids)
      current = set(context_ids)

      while len(current) > 0:
        new_current = set()
        for ctx_id in (ctx_id for par_id in current for ctx_id in context_children.get(par_id, [])):
          if not ctx_id in total: new_current.add(ctx_id)
        total.update(new_current)
        current = new_current

      total.difference_update(context_ids)
      return total

  def _get_context_parents(self, context_id: str):
    parent_id = context_id
    while (parent_id := self._context_parents.get(parent_id)) is not None: yield parent_id

  @staticmethod
  def get_hashed_id(raw: str): return base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest()).decode("utf-8")

class Context:
  def __init__(self, id: str, execution: AppExecution) -> None:
    self.id = id
    self.execution = execution

  @property
  def query_string(self): return self.execution.execution_input.query_string

  @property
  def path(self): return self.execution.execution_input.path

  @property
  def headers(self): return self.execution.executor.headers

  def get_events(self): return self.execution.get_context_events(self.id)

  async def get_state(self, name: str, state_factory: StateFactory, is_global: bool = False):
    context = Context("", self.execution) if is_global else self
    state = await self.execution.executor.get_state(name, context, state_factory)
    self.execution.state_users.setdefault(state, []).append(self.id)
    return state

  def navigate(self, location: str): self.execution.output_events.append(NavigateOutputEvent(location=location))
  def use_websocket(self, websocket: bool = True): self.execution.output_events.append(UseWebsocketOutputEvent(websocket=websocket))
  def get_cookie(self, name: str) -> str | None: return self.execution.executor.cookies.get(name, None)
  def set_cookie(self, name: str, value: str, expires: datetime | None = None, path: str | None = None,
                secure: bool | None = None, http_only: bool | None = None, domain: str | None = None, max_age: int | None = None):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, value=value, expires=expires, path=path, secure=secure, http_only=http_only, domain=domain, max_age=max_age))
  def delete_cookie(self, name: str):
    self.execution.output_events.append(SetCookieOutputEvent(name=name, max_age=-1))

  def sub_element(self, el: Element):
    context = self.sub(el.__class__.__qualname__)
    self.execution.context_elements[context.id] = el
    return context

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(id=self.execution.get_context_id(self.id, key), execution=self.execution)
