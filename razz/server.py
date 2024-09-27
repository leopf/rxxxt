from abc import ABC, abstractmethod
import asyncio
import base64
from dataclasses import dataclass
from inspect import isawaitable
import inspect
import json
import secrets
import sys
from typing import Annotated, Callable, Generic, ParamSpec, TypeVar, Union, get_args, get_origin, get_type_hints, Awaitable
import weakref
# from razz.asgiserver import
from pydantic import BaseModel, Field, create_model
from pydantic_core import PydanticUndefined

T = TypeVar("T")
async def to_awaitable(fn: Callable[..., T | Awaitable[T]], *args, **kwargs) -> T:
  result = fn(*args, **kwargs)
  if isawaitable(result): result = await result
  return result

def validate_key(key: str):
  if ";" in key: raise ValueError("Key must not contain a semicolon.")
  if "!" in key: raise ValueError("Key must not contain an exclamation mark.")
  if "#" in key: raise ValueError("Key must not contain a hashtag.")

class State(BaseModel):
  def init(self) -> None | Awaitable[None]: pass

@dataclass
class ContextEventTokenData:
  context_id: str
  handler_name: str
  allowed_fields: list[str]

@dataclass
class ContextEvent:
  context_id: str
  handler_name: str
  data: dict[str, int | float | str | bool]

@dataclass
class AppInputData:
  state: dict[str, str]
  events: list[ContextEvent]

@dataclass
class AppOuputData:
  state: dict[str, str]
  events: list

class AppExecution:
  def __init__(self, input_data: AppInputData) -> None:
    self._unique_ids: set[str] = set()
    self._state: dict[str, State] = {}
    self._input_state = input_data.state
    self._input_events: dict[str, list[ContextEvent]] = { e.context_id: [] for e in input_data.events }
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

  def get_context_events(self, context_id: str):
    for e in self._input_events.get(context_id, []): yield e

  async def get_state(self, name: str, context: str, state_type: type[State]):
    key = context + "!" + name
    if key in self._state:
      state = self._state[key]
      if not isinstance(state, state_type): raise ValueError("Invalid state type for state!")
    elif key in self._input_state:
      raw_state = self._input_state[key]
      state = state_type.model_validate_json(raw_state)
      self._state[key] = state
    else:
      state = self._state[key] = state_type()
      await to_awaitable(state.init) # basically useless for now but lets keep it for later
    return state

  def get_output_data(self) -> AppOuputData:
    return AppOuputData(
      state={ k: v.model_dump_json() for k, v in self._state.items() },
      events=[]
    )

class Context:
  def __init__(self, keyspace: str, execution: AppExecution) -> None:
    self.keyspace = keyspace
    self.execution = execution

  def get_context_id(self): return self.execution.get_context_id(self.keyspace)

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(keyspace=self.keyspace + ";" + key, execution=self.execution)

@dataclass
class PartialStateInfo:
  is_global: bool
  name: str | None

@dataclass
class StateInfo:
  is_global: bool
  attr_name: str
  state_name: str
  state_type: type[State]

def global_state(name: str): return PartialStateInfo(is_global=True, name=name)

EHP = ParamSpec('EHP')
EHR = TypeVar('EHR')

class Element(ABC):
  @abstractmethod
  async def to_html(self, context: Context) -> str: pass

class CustomAttribute(ABC):
  @abstractmethod
  def get_key(self, original_key: str) -> str: pass

  @abstractmethod
  def get_value(self) -> str: pass

class HTMLElement(Element):
  def __init__(self, tag: str, attributes: dict[str, str | CustomAttribute], content: list[Union[Element, str]], key: str | None = None) -> None:
    super().__init__()
    self.tag = tag
    self.key = key
    self.attributes = attributes
    self.content = content

  async def to_html(self, context: Context) -> str:
    if self.key is not None:
      context = context.sub(self.key)

    parts: list[str] = []
    for item in self.content:
      if isinstance(item, Element): parts.append(await item.to_html(context))
      else: parts.append(item)

    inner_html = "".join(parts)

    attributes = dict((k, v) if isinstance(v, str) else (v.get_key(k), v.get_value()) for k, v in self.attributes.items())
    attribute_str = "".join(f" {k}=\"{v}\"" for k, v in attributes.items())
    return f"<{self.tag}{attribute_str}>{inner_html}</{self.tag}>"

class ClassEventHandler(Generic[EHP, EHR]):
  _fn_spec_cache: weakref.WeakKeyDictionary[Callable, tuple[BaseModel, dict[int, str], dict[str, str]]] = weakref.WeakKeyDictionary()

  def __init__(self, fn:  Callable[EHP, EHR]) -> None:
    self.fn = fn
    self.instance: object | None = None

  def __get__(self, instance, owner):
    self.instance = instance
    return self

  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR:
    if len(args) == 0: raise ValueError("Expected at least self as a positional argument.")
    model, arg_map, _ = self._get_function_specs()
    params = {**kwargs}
    for i, arg in enumerate(args):
      i = i + 1
      if i not in arg_map:
        raise ValueError(f"Argument {i} is not allowed!")
      params[arg_map[i]] = arg

    new_kwargs = model.model_validate(params).model_dump()
    return self.fn(self.instance, **new_kwargs)

  @staticmethod
  def _is_valid_type(typ, valid_types):
    origin = get_origin(typ)
    if origin is Union:
      return all(ClassEventHandler._is_valid_type(arg, valid_types) for arg in get_args(typ))
    return issubclass(typ, valid_types)

  def _get_function_specs(self):
    specs = ClassEventHandler._fn_spec_cache.get(self.fn, None)
    if specs is not None: return specs

    valid_types = (str, float, int, bool)

    fields: dict[str, tuple[type, Field]] = {}
    args_map: dict[int, str] = {}
    annotation_map: dict[str, str] = {}

    sig = inspect.signature(self.fn)

    for i, (name, param) in enumerate(sig.parameters.items()):
      if i == 0: continue # skip self

      if get_origin(param.annotation) is Annotated:
        args = get_args(param.annotation)
        main_type = args[0]
        metadata = args[1:]

        if not ClassEventHandler._is_valid_type(main_type, valid_types):
            raise TypeError(f"The type of parameter '{name}' is not allowed. Must be str, float, int, or bool.")

        if len(metadata) < 1:
            raise ValueError(f"Parameter '{name}' is missing the second annotation.")

        field_default = PydanticUndefined if param.default is param.empty else param.default
        fields[name] = (main_type, Field(description=metadata[0], default=field_default))

        args_map[i] = name

        annotation_map[name] = metadata[0]
      else:
        raise TypeError(f"Parameter '{name}' must be of type Annotated.")

    model: BaseModel = create_model(f"{self.fn.__name__}Model", **fields)
    spec = model, args_map, annotation_map
    ClassEventHandler._fn_spec_cache[self.fn] = spec
    return spec


class InstanceEventHandler(ClassEventHandler, Generic[EHP, EHR], CustomAttribute):
  def __init__(self, fn:  Callable[EHP, EHR], context_id: str, execution: AppExecution, instance: object) -> None:
    self.fn = fn
    self.context_id = context_id
    self.execution = execution
    self.instance = instance
  def get_key(self, original_key: str) -> str: return f"razz-on-{original_key}"
  def get_value(self) -> str:
    _, _, param_map = self._get_function_specs()
    print(param_map)
    return base64.b64encode(json.dumps({
      "context_id": self.context_id,
      "handler_name": self.fn.__name__,
      "param_map": param_map
    }).encode("utf-8")).decode("utf-8")

def event_handler(fn): return ClassEventHandler(fn)

class Component(Element, ABC):
  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: pass
  def init(self) -> None | Awaitable[None]: pass

  async def to_html(self, context: Context) -> str:
    context = context.sub(self.__class__.__qualname__)
    context_id = context.get_context_id()

    # setup

    for attr_name in dir(self):
      if not attr_name.startswith("_"):
        v = getattr(self, attr_name)
        if isinstance(v, ClassEventHandler):
          setattr(self, attr_name, InstanceEventHandler(v.fn, context_id, context.execution, v.instance))

    for state_info in self._get_state_infos():
      state_context_id = "" if state_info.is_global else context_id
      state = await context.execution.get_state(state_info.state_name, state_context_id, state_info.state_type)
      setattr(self, state_info.attr_name, state)

    # run

    await to_awaitable(self.init)
    result = await to_awaitable(self.render)

    # to text

    return await result.to_html(context)

  @classmethod
  def _get_state_infos(cls):
    global_ns = vars(sys.modules[cls.__module__])
    for base_class in reversed(cls.__mro__):
      type_hints = get_type_hints(base_class, globalns=global_ns)
      for attr_name, attr_type in type_hints.items():
        if isinstance(attr_type, type) and issubclass(attr_type, State):
          if hasattr(cls, attr_name):
            partial_state_info = getattr(cls, attr_name)
            if not isinstance(partial_state_info, PartialStateInfo):
              raise ValueError("State field must not be defined as anything but a PartialStateInfo in the class.")
            yield StateInfo(is_global=partial_state_info.is_global, attr_name=attr_name, state_name=partial_state_info.name or attr_name, state_type=attr_type)
          else:
            yield StateInfo(is_global=False, state_name=attr_name, attr_name=attr_name, state_type=attr_type)

class TestState(State):
  count: int = 0

class AuthState(State):
  username: str = secrets.token_hex(6)

class HomePage(Component):
  state: TestState
  auth: AuthState = global_state("auth")

  def __init__(self, title: str) -> None:
    super().__init__()
    self.title = title
    self.la = secrets.token_hex(5)

  @event_handler
  def on_click(self, value: Annotated[str, "0.target.value"]):
    print("DID the value thingy", value)

  def render(self):
    self.on_click("HHHHEEEE" + self.la)
    return HTMLElement("div", { "class": "comp", "click": self.on_click }, content=[self.title, str(self.state.count), "  ", self.auth.username])


def index(auth : State):
  return Component()

async def main():
  context = Context("", AppExecution(AppInputData(state={}, events=[])))

  print(await HTMLElement("div", { "class": "hello-world" }, [ "Hello", HTMLElement("b", {}, [ "World!" ]), HomePage("WOOOOO"), HomePage("WAAAAA") ]).to_html(context))

  print(context.execution.get_output_data())

asyncio.run(main())
