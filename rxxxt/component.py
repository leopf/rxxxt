from abc import ABC, abstractmethod
import base64
import inspect
import json
from types import NoneType, UnionType
from typing import Annotated, Any, Awaitable, Callable, Generic, ParamSpec, TypeVar, get_args, get_origin
import weakref
from pydantic import BaseModel, Field, create_model
from pydantic_core import PydanticUndefined

from rxxxt.elements import CustomAttribute, Element
from rxxxt.execution import Context
from rxxxt.helpers import to_awaitable
from rxxxt.state import StateBase, get_state_infos_for_object_type

EHP = ParamSpec('EHP')
EHR = TypeVar('EHR')

class EventHandlerOptions(BaseModel):
  debounce: int | None = None
  throttle: int | None = None
  prevent_default: bool = False

class ClassEventHandler(Generic[EHP, EHR]):
  def __init__(self, fn:  Callable[EHP, EHR], options: EventHandlerOptions) -> None:
    self.fn = fn
    self.options = options
  def __get__(self, instance, owner): return InstanceEventHandler(self.fn, self.options, instance)
  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: raise RuntimeError("The event handler can only be called when attached to an instance!")

class InstanceEventHandler(ClassEventHandler, Generic[EHP, EHR], CustomAttribute):
  _fn_spec_cache: weakref.WeakKeyDictionary[Callable, tuple[BaseModel, dict[int, str], dict[str, str]]] = weakref.WeakKeyDictionary()
  _valid_types = (str, float, int, bool)

  def __init__(self, fn: Callable[EHP, EHR], options: EventHandlerOptions, instance: Any) -> None:
    super().__init__(fn, options)
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
    if not original_key.startswith("on"): raise ValueError("Event handler must be applied to an attribute starting with 'on'.")
    if self.instance.context is None: raise ValueError("The instance must have a context_id to create an event value.")
    _, _, param_map = self._get_function_specs()
    v = base64.b64encode(json.dumps({
      "context_id": self.instance.context.id,
      "handler_name": self.fn.__name__,
      "param_map": param_map,
      "options": self.options.model_dump(exclude_defaults=True)
    }).encode("utf-8")).decode("utf-8")
    return (f"rxxxt-on-{original_key[2:]}", v)

  @staticmethod
  def _is_valid_type(typ):
    if typ is NoneType: return True
    origin = get_origin(typ)
    if origin is UnionType:
      return all(InstanceEventHandler._is_valid_type(arg) for arg in get_args(typ))
    return issubclass(typ, InstanceEventHandler._valid_types)

  def _get_function_specs(self):
    specs = InstanceEventHandler._fn_spec_cache.get(self.fn, None)
    if specs is not None: return specs

    fields: dict[str, tuple[type, Field]] = {}
    args_map: dict[int, str] = {}
    param_map: dict[str, str] = {}

    sig = inspect.signature(self.fn)

    for i, (name, param) in enumerate(sig.parameters.items()):
      if i == 0: continue # skip self

      if get_origin(param.annotation) is Annotated:
        args = get_args(param.annotation)
        main_type = args[0]
        metadata = args[1:]

        if not InstanceEventHandler._is_valid_type(main_type):
          raise TypeError(f"The type of parameter '{name}' is not allowed. Must be str, float, int, or bool.")

        if len(metadata) < 1:
          raise ValueError(f"Parameter '{name}' is missing the second annotation.")

        field_default = PydanticUndefined if param.default is param.empty else param.default
        fields[name] = (main_type, Field(description=metadata[0], default=field_default))
        args_map[i] = name
        param_map[name] = metadata[0]
      else:
        raise TypeError(f"Parameter '{name}' must be of type Annotated.")

    model: BaseModel = create_model(f"{self.fn.__name__}Model", **fields)
    spec = model, args_map, param_map
    InstanceEventHandler._fn_spec_cache[self.fn] = spec
    return spec

def event_handler(**kwargs):
  options = EventHandlerOptions.model_validate(kwargs)
  def _inner(fn): return ClassEventHandler(fn, options)
  return _inner

class Component(Element, ABC):
  def __init__(self) -> None:
    super().__init__()
    self.context: Context

  @abstractmethod
  def render(self) -> Element: pass
  def init(self) -> None | Awaitable[None]: pass

  async def to_html(self, context: Context) -> str:
    self.context = context.sub(self.__class__.__qualname__)

    for state_info in get_state_infos_for_object_type(self.__class__):
      self.__dict__[state_info.attr_name] = await self.context.get_state(state_info.state_name, state_info.state_maker, state_info.is_global)

    for e in self.context.pop_events():
      handler = getattr(self, e.handler_name, None)
      if isinstance(handler, InstanceEventHandler):
        await to_awaitable(handler, **e.data)
      else:
        raise ValueError("Invalid event handler.")

    # run

    await to_awaitable(self.init)
    result = self.render()

    # to text

    return await result.to_html(self.context)

  def __getattribute__(self, name: str) -> Any:
    if name != "__dict__":
      _pstate = self.__dict__.get(name, None)
      if isinstance(_pstate, StateBase): return _pstate.get_value()
    return super().__getattribute__(name)

  def __setattr__(self, name: str, value: Any) -> NoneType:
    _pstate = self.__dict__.get(name, None)
    if isinstance(_pstate, StateBase): return _pstate.set_value(value)
    return super().__setattr__(name, value)
