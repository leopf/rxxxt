from abc import ABC, abstractmethod
import asyncio
import base64
from dataclasses import dataclass
from inspect import isawaitable
import inspect
import json
import secrets
import sys
from typing import Annotated, Any, Callable, Generic, ParamSpec, TypeVar, Union, get_args, get_origin, get_type_hints, Awaitable
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

class State(BaseModel): pass

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

  def pop_context_events(self, context_id: str): return self._input_events.pop(context_id, [])

  def get_state(self, name: str, context: str, state_type: type[State]):
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
    return state

  def get_output_data(self) -> AppOuputData:
    return AppOuputData(
      state={ k: v.model_dump_json() for k, v in self._state.items() },
      events=[]
    )

class Context:
  def __init__(self, id: str, execution: AppExecution) -> None:
    self.id = id
    self.execution = execution

  def pop_events(self): return self.execution.pop_context_events(self.id)

  def sub(self, key: str) -> 'Context':
    validate_key(key)
    return Context(id=self.execution.get_context_id(self.id + ";" + key), execution=self.execution)

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

class Element(ABC):
  @abstractmethod
  async def to_html(self, context: Context) -> str: pass

class CustomAttribute(ABC):
  @abstractmethod
  def get_html_attribute_key_value(self, original_key: str) -> str: pass

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

    attributes = dict((k, v) if isinstance(v, str) else v.get_html_attribute_key_value(k) for k, v in self.attributes.items())
    attribute_str = "".join(f" {k}=\"{v}\"" for k, v in attributes.items())
    return f"<{self.tag}{attribute_str}>{inner_html}</{self.tag}>"

EHP = ParamSpec('EHP')
EHR = TypeVar('EHR')

class ClassEventHandler(Generic[EHP, EHR]):
  def __init__(self, fn:  Callable[EHP, EHR]) -> None: self.fn = fn
  def __get__(self, instance, owner): return InstanceEventHandler(self.fn, instance)
  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: raise RuntimeError("The event handler can only be called when attached to an instance!")

class InstanceEventHandler(ClassEventHandler, Generic[EHP, EHR], CustomAttribute):
  _fn_spec_cache: weakref.WeakKeyDictionary[Callable, tuple[BaseModel, dict[int, str], dict[str, str]]] = weakref.WeakKeyDictionary()
  
  def __init__(self, fn: Callable[EHP, EHR], instance: Any) -> None:
    super().__init__(fn)
    if not isinstance(instance, Component): raise ValueError("The provided instance must be a component!")
    self.instance = instance

  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR:
    model, arg_map, _ = self._get_function_specs()
    params = {**kwargs}
    for i, arg in enumerate(args):
      i = i + 1
      if i not in arg_map:
        raise ValueError(f"Argument {i} is not allowed!")
      params[arg_map[i]] = arg

    new_kwargs = model.model_validate(params).model_dump()
    return self.fn(self.instance, **new_kwargs)

  def get_html_attribute_key_value(self, original_key: str):
    if self.instance.context is None: raise ValueError("The instance must have a context_id to create an event value.")
    _, _, param_map = self._get_function_specs()
    v = base64.b64encode(json.dumps({
      "context_id": self.instance.context.id,
      "handler_name": self.fn.__name__,
      "param_map": param_map
    }).encode("utf-8")).decode("utf-8")
    return (f"razz-on-{original_key}", v)
    
  @staticmethod
  def _is_valid_type(typ, valid_types):
    origin = get_origin(typ)
    if origin is Union:
      return all(InstanceEventHandler._is_valid_type(arg, valid_types) for arg in get_args(typ))
    return issubclass(typ, valid_types)

  def _get_function_specs(self):
    specs = InstanceEventHandler._fn_spec_cache.get(self.fn, None)
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

        if not InstanceEventHandler._is_valid_type(main_type, valid_types):
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
    InstanceEventHandler._fn_spec_cache[self.fn] = spec
    return spec

def event_handler(fn): return ClassEventHandler(fn)

class Component(Element, ABC):
  def __init__(self) -> None:
    super().__init__()
    self.context: Context | None = None
  
  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: pass
  def init(self) -> None | Awaitable[None]: pass

  async def to_html(self, context: Context) -> str:
    self.context = context.sub(self.__class__.__qualname__)
    
    for state_info in self._get_state_infos():
      setattr(self, state_info.attr_name, self.get_state(state_info.state_name, state_info.state_type, state_info.is_global))

    for e in self.context.pop_events():
      handler = getattr(self, e.handler_name, None)
      if isinstance(handler, InstanceEventHandler):
        await to_awaitable(handler, **e.data)
      else:
        raise ValueError("Invalid event handler.")

    # run

    await to_awaitable(self.init)
    result = await to_awaitable(self.render)

    # to text

    return await result.to_html(self.context)

  def get_state(self, name: str, state_type: type[State], is_global: bool = False):
    state_context_id = "" if is_global else self.context.id
    return self.context.execution.get_state(name, state_context_id, state_type)

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
  username: str = Field(default_factory=lambda: secrets.token_hex(6))

class HomePage(Component):
  state: TestState
  auth: AuthState = global_state("auth")

  def __init__(self, title: str) -> None:
    super().__init__()
    self.title = title
    self.la = secrets.token_hex(5)

  @event_handler
  def on_click(self, value: Annotated[str, "0.target.value"]):
    print("DID the value thingy", value, self.la)
    self.state.count += 1

  def render(self):
    return HTMLElement("div", { "class": "comp", "click": self.on_click }, content=[self.title, str(self.state.count), "  ", self.auth.username])


def index(auth : State):
  return Component()

async def main():
  context = Context("", AppExecution(AppInputData(state={}, events=[
    ContextEvent(";HomePage#0", "on_click", { "value": "MAIN TEST" })
  ])))

  print(await HTMLElement("div", { "class": "hello-world" }, [ "Hello", HTMLElement("b", {}, [ "World!" ]), HomePage("WOOOOO"), HomePage("WAAAAA") ]).to_html(context))

  print(context.execution.get_output_data())

asyncio.run(main())
