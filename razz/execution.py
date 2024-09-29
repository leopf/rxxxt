from dataclasses import dataclass
import hashlib
from typing import Literal

from razz.elements import Element
from razz.state import State


def validate_key(key: str):
  if ";" in key: raise ValueError("Key must not contain a semicolon.")
  if "!" in key: raise ValueError("Key must not contain an exclamation mark.")
  if "#" in key: raise ValueError("Key must not contain a hashtag.")

@dataclass
class ContextInputEvent:
  context_id: str
  handler_name: str
  data: dict[str, int | float | str | bool]

@dataclass
class SetCookieOutputEvent:
  event: Literal["set-cookie"] = "set-cookie"

@dataclass
class ForceRefreshOutputEvent:
  event: Literal["force-refresh"] = "force-refresh"

@dataclass
class NavigateOutputEvent:
  location: str
  event: Literal["navigate"] = "navigate"

ExecutionOutputEvent = SetCookieOutputEvent | NavigateOutputEvent

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

  async def execute(self, element: 'Element', exec_input: ExecutionInput):
    execution = AppExecution(self, exec_input)
    context_prefix = hashlib.sha1(exec_input.path.encode("utf-8")).hexdigest()
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

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(id=self.execution.get_context_id(self.id + ";" + key), execution=self.execution)
