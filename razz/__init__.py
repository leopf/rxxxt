from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
import datetime
import hashlib
import html
import importlib.resources
from inspect import isawaitable
import inspect
import json
import sys
from types import NoneType
from typing import Annotated, Any, Callable, Generic, Literal, ParamSpec, TypeVar, Union, get_args, get_origin, get_type_hints, Awaitable
import weakref
from pydantic import BaseModel, Field, TypeAdapter, create_model
from pydantic_core import PydanticUndefined
from razz.asgi import ASGIFnReceive, ASGIFnSend, ASGIScope, HTTPContext
from razz.helpers import PathPattern
import jwt

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

ElementFactory = Callable[[], 'Element']

class AppExecutor:
  def __init__(self, raw_state: dict[str, str], headers: dict[str, list[str]]) -> None:
    self._raw_state = raw_state
    self._headers = headers
    self._state: dict[str, State] = {}

  async def execute(self, element: 'Element', exec_input: ExecutionInput):
    execution = AppExecution(self, exec_input)
    context_prefix = hashlib.sha1(exec_input.path.encode("utf-8")).hexdigest()
    html = await element.to_html(Context(context_prefix, execution))
    return html, execution.output_events

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

class CustomAttribute(ABC):
  @abstractmethod
  def get_html_attribute_key_value(self, original_key: str) -> str: pass

class Element(ABC):
  @abstractmethod
  async def to_html(self, context: Context) -> str: pass

class HTMLFragment(Element):
  def __init__(self, content: list[Union[Element, str]], key: str | None = None) -> None:
    super().__init__()
    self.key = key
    self.content = content

  async def to_html(self, context: Context) -> str:
    if self.key is not None:
      context = context.sub(self.key)

    parts: list[str] = []
    for item in self.content:
      if isinstance(item, Element): parts.append(await item.to_html(context))
      else: parts.append(html.escape(str(item), quote=False))

    return "".join(parts)

class HTMLBaseElement(Element):
  def __init__(self, tag: str, attributes: dict[str, str | CustomAttribute | NoneType]) -> None:
    super().__init__()
    self.tag = tag
    self.attributes = attributes

  def _render_attributes(self):
    parts: list[str] = []
    for k, v in self.attributes.items():
      if isinstance(v, CustomAttribute): k, v = v.get_html_attribute_key_value(k)
      k = html.escape(str(k))
      if v is not None: v = html.escape(str(v))
      if v is None: parts.append(f" {k}")
      else: parts.append(f" {k}=\"{v}\"")
    return "".join(parts)

class HTMLVoidElement(HTMLBaseElement):
  async def to_html(self, context: Context) -> str:
    return f"<{html.escape(self.tag)}{self._render_attributes()}>"

class HTMLElement(HTMLBaseElement):
  def __init__(self, tag: str, attributes: dict[str, str | CustomAttribute | NoneType] = {}, content: list[Union[Element, str]] = [], key: str | None = None) -> None:
    super().__init__(tag, attributes)
    self.key = key
    self.content = content

  async def to_html(self, context: Context) -> str:
    if self.key is not None:
      context = context.sub(self.key)

    parts: list[str] = []
    for item in self.content:
      if isinstance(item, Element): parts.append(await item.to_html(context))
      else: parts.append(html.escape(str(item), quote=False))

    inner_html = "".join(parts)
    tag = html.escape(self.tag)
    return f"<{tag}{self._render_attributes()}>{inner_html}</{tag}>"

EHP = ParamSpec('EHP')
EHR = TypeVar('EHR')

class EventHandlerOptions(BaseModel):
  pass

class ClassEventHandler(Generic[EHP, EHR]):
  def __init__(self, fn:  Callable[EHP, EHR], options: EventHandlerOptions) -> None:
    self.fn = fn
    self.options = options
  def __get__(self, instance, owner): return InstanceEventHandler(self.fn, self.options, instance)
  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: raise RuntimeError("The event handler can only be called when attached to an instance!")

class InstanceEventHandler(ClassEventHandler, Generic[EHP, EHR], CustomAttribute):
  _fn_spec_cache: weakref.WeakKeyDictionary[Callable, tuple[BaseModel, dict[int, str], dict[str, str]]] = weakref.WeakKeyDictionary()

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
      "options": self.options.model_dump()
    }).encode("utf-8")).decode("utf-8")
    return (f"razz-on-{original_key[2:]}", v)

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

def event_handler(**kwargs):
  options = EventHandlerOptions.model_validate(kwargs)
  def _inner(fn): return ClassEventHandler(fn, options)
  return _inner

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
      setattr(self, state_info.attr_name, self.context.get_state(state_info.state_name, state_info.state_type, state_info.is_global))

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

class AppHttpRequest(BaseModel):
  state_token: str
  events: list[ContextInputEvent]

class AppHttpResult(BaseModel):
  state_token: str
  events: list[ExecutionOutputEvent]

class AppHttpPostResponse(AppHttpResult):
  html: str

RawStateAdapter = TypeAdapter(dict[str, str])

class App:
  def __init__(self, jwt_secret: bytes, session_duration: datetime.timedelta | None = None, jwt_algorithm: str = "HS512") -> None:
    self._routes: list[tuple[PathPattern, ElementFactory]]

    self._session_duration = datetime.timedelta(hours=1) if session_duration is None else session_duration
    self._jwt_secret = jwt_secret
    if not jwt_algorithm.startswith("HS"): raise ValueError("JWT algorithm must start with HS")
    self._jwt_algorithm = jwt_algorithm

  def add_route(self, path: str, element_factory: ElementFactory): self._routes.append((PathPattern(path), element_factory))
  def route(self, path: str):
    def _inner(fn: ElementFactory):
      self.add_route(path, fn)
      return fn
    return _inner

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] == "http":
      return await self._handle_http(HTTPContext(scope, receive, send))

  async def _handle_http(self, context: HTTPContext):
    if context.path == "/razz-client.js":
      with importlib.resources.path("razz.assets", "main.js") as file_path:
        return await context.respond_file(file_path)

    if context.method in [ "GET", "POST" ] and (route := self._get_route(context.path)) is not None:
      params, element_factory = route

      if context.method == "POST":
        req = AppHttpRequest.model_validate_json(await context.receive_json_raw())
        state, events = self._verify_state(req.state_token), req.events
      else: state, events={}, []

      executor = AppExecutor(state, context.headers)

      html, output_events = await executor.execute(element_factory(), ExecutionInput(
        events=events,
        params=params,
        path=context.path,
        query_string=context.query_string
      ))

      # TODO: handle output events

      if len(events) > 0:
        if len(output_events) > 0: output_events.append(ForceRefreshOutputEvent())
        else:
          html, output_events = await executor.execute(element_factory(), ExecutionInput(
            params=params,
            path=context.path,
            query_string=context.query_string
          ))

      if context.method == "POST":
        await context.respond_json_string(AppHttpPostResponse(
          state_token=self._sign_state(executor.get_raw_state()),
          events=output_events,
          html=html
        ))
      else:
        pass



    else: await context.respond_status(404)

  # def _render_page()

  def _sign_state(self, state: dict[str, str]):
    return jwt.encode({ "data": state, "exp": datetime.datetime.now(tz=datetime.timezone.utc) + self._session_duration}, self._jwt_secret, self._jwt_algorithm)

  def _verify_state(self, token: str):
    token_data = jwt.decode(token, self._jwt_secret, algorithms=[self._jwt_algorithm])
    return RawStateAdapter.validate_python(token_data["data"])

  def _get_route(self, path: str):
    for pattern, element_factory in self._routes:
      if (match := pattern.match(path)) is not None:
        return match, element_factory
    return None
