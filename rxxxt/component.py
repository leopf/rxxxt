import asyncio, inspect, weakref, html, functools
from abc import abstractmethod
from typing import Annotated, Any, Callable, Concatenate, Generic, get_args, get_origin, get_type_hints
from collections.abc import Awaitable, Coroutine
from pydantic import validate_call, TypeAdapter
from rxxxt.elements import CustomAttribute, Element, meta_element
from rxxxt.execution import Context, InputEventDescriptorOptions
from rxxxt.helpers import attribute_key_to_event_name, to_awaitable, FNP, FNR, T
from rxxxt.node import EventHandlerNode, Node, TextNode
from rxxxt.state import StateCell, State

class StateBox(Generic[T], StateCell):
  def __init__(self, key: str, state: State, default_factory: Callable[[], T], adapter: TypeAdapter[T]) -> None:
    super().__init__()
    self._key = key
    self._state = state
    self._adapter = adapter
    self._value: T

    key_state = state.get(key)
    key_state.add_consumer(self)
    try: self._value = adapter.validate_json(key_state.get())
    except ValueError:
      self._value = default_factory()
      key_state.set(self)

  def __enter__(self): return self.value
  def __exit__(self, *_): self.update()

  @property
  def key(self): return self._key

  @property
  def value(self): return self._value

  @value.setter
  def value(self, v: T):
    self._value = v
    self.update()

  def update(self):
    self._state.get(self._key).set(self)

  def produce(self, key: str) -> str:
    return self._adapter.dump_json(self._value).decode()

  def consume(self, key: str, producer: Callable[[], str]) -> Any:
    self._value = self._adapter.validate_json(producer())

  def detach(self, key: str) -> Any:
    del self._value

class StateBoxDescriptorBase(Generic[T]):
  def __init__(self, state_key_producer: Callable[[Context, str], str], default_factory: Callable[[], T], state_name: str | None = None) -> None:
    self._state_name = state_name
    self._default_factory = default_factory
    self._state_key_producer = state_key_producer
    self._box_cache: weakref.WeakKeyDictionary[Context, StateBox] = weakref.WeakKeyDictionary()

    native_types = (bool, bytearray, bytes, complex, dict, float, frozenset, int, list, object, set, str, tuple)
    if default_factory in native_types or get_origin(default_factory) in native_types:
      self._val_type_adapter: TypeAdapter[Any] = TypeAdapter(default_factory)
    else:
      sig = inspect.signature(default_factory)
      self._val_type_adapter = TypeAdapter(sig.return_annotation)

  def __set_name__(self, owner: Any, name: str):
    if self._state_name is None:
      self._state_name = name

  def _get_box(self, context: Context) -> StateBox[T]:
    if not self._state_name: raise ValueError("State name not defined!")
    key = self._state_key_producer(context, self._state_name)
    context.subscribe(key)

    if (box := self._box_cache.get(context)) is None:
      box = StateBox(key, context.state, self._default_factory, self._val_type_adapter)
      self._box_cache[context] = box

    return box

class StateBoxDescriptor(StateBoxDescriptorBase[T]):
  def __get__(self, obj: Any, objtype: Any=None):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    obj.context.subscribe(box.key)

    return box

class StateDescriptor(StateBoxDescriptorBase[T]):
  def __set__(self, obj: Any, value: Any):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    obj.context.subscribe(box.key)

    box.value = value

  def __get__(self, obj: Any, objtype: Any=None):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    obj.context.subscribe(box.key)

    return box.value

def get_global_state_key(_context: Context, name: str):
  return f"global;{name}"

def get_local_state_key(context: Context, name: str):
  return f"#local;{context.sid};{name}"

def get_context_state_key(context: Context, name: str):
  state_key = None
  exisiting_keys = context.state.keys
  for sid in context.stack_sids:
    state_key = f"#context;{sid};{name}"
    if state_key in exisiting_keys:
      return state_key
  if state_key is None: raise ValueError(f"State key not found for context '{name}'!")
  return state_key # this is just the key for context.sid

def local_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_local_state_key, default_factory, state_name=name)

def global_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_global_state_key, default_factory, state_name=name)

def context_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_context_state_key, default_factory, state_name=name)

def local_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_local_state_key, default_factory, state_name=name)

def global_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_global_state_key, default_factory, state_name=name)

def context_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_context_state_key, default_factory, state_name=name)

class SharedExternalState(Generic[T]):
  def __init__(self, initial_value: T) -> None:
    self._components: weakref.WeakSet[Component] = weakref.WeakSet()
    self._value: T = initial_value

  @property
  def value(self) -> T:
    return self._value

  @value.setter
  def value(self, nv: T):
    self._value = nv
    self.update()

  def __get__(self, obj: Any, objtype: Any=None):
    if obj is None:
      return self
    if not isinstance(obj, Component):
      raise TypeError("SharedExternalState must only be accessed from inside a component!")
    self._components.add(obj)
    return self

  def update(self):
    for component in self._components:
      component.context.request_update()

class BoundEventHandler(Generic[FNP, FNR], CustomAttribute):
  def __init__(self, bound: tuple[Any,...], handler: Callable[Concatenate[Any, FNP], FNR], options: InputEventDescriptorOptions) -> None:
    super().__init__()
    self._bound = bound
    self._handler = validate_call(handler)
    self._options = options.model_copy(update={'param_map': BoundEventHandler.get_handler_param_map(len(bound), handler) | options.param_map})

  def __call__(self, *args: FNP.args, **kwds: FNP.kwargs) -> FNR:
    return self._handler(*self._bound, *args, **kwds)

  def tonode(self, context: Context, original_key: str) -> Node:
    return EventHandlerNode(context, attribute_key_to_event_name(original_key), functools.partial(self._handler, *self._bound), self._options)

  @staticmethod
  def get_handler_param_map(n_bound: int, handler: Callable):
    param_map: dict[str, str] = {}
    sig = inspect.signature(handler)
    hints = get_type_hints(handler, include_extras=True)
    for i, (name, param) in enumerate(sig.parameters.items()):
      if i < n_bound: continue  # skip self
      ann = hints.get(name, param.annotation)
      if get_origin(ann) is Annotated:
        args = get_args(ann)
        metadata = args[1:]
        if len(metadata) < 1:
          raise ValueError(f"Parameter '{name}' is missing the second annotation.")
        if not isinstance(metadata[0], str):
          raise TypeError(f"Parameter '{name}' second annotation must be a str, got {type(metadata[0]).__name__}.")
        param_map[name] = metadata[0]
    return param_map

class UnboundEventHandler(Generic[FNP, FNR]):
  def __init__(self, handler: Callable[Concatenate[Any, FNP], FNR], options: InputEventDescriptorOptions) -> None:
    super().__init__()
    self._handler = handler
    self._options = options

  def __get__(self, instance: Any, _):
    return BoundEventHandler((instance,), self._handler, self._options)

  def __call__(self, instance: Any, *args: FNP.args, **kwds: FNP.kwargs) -> FNR:
    return self._handler(instance, *args, **kwds)

def event_handler(**kwargs: Any):
  options = InputEventDescriptorOptions.model_validate(kwargs)
  def _inner(fn: Callable[Concatenate[Any, FNP], FNR]) -> UnboundEventHandler[FNP, FNR]: return UnboundEventHandler(fn, options)
  return _inner

class HandleNavigate(CustomAttribute):
  def __init__(self, location: str) -> None:
    super().__init__()
    self.location = location

  def tonode(self, context: Context, original_key: str) -> Node:
    return TextNode(context, f"{html.escape(original_key)}=\"window.rxxxt.navigate('{html.escape(self.location)}');\"")

class Component(Element):
  def __init__(self) -> None:
    super().__init__()
    self.context: Context
    self._worker_tasks: list[asyncio.Task[Any]] = []
    self._job_tasks: list[asyncio.Task[Any]] = []

  def add_job(self, a: Coroutine[Any, Any, Any]):
    """
    Runs a background job until completion. Only runs when the session is persistent.
    args:
      a: Coroutine - the coroutine that should be run
    """
    if self.context.config.persistent:
      self._worker_tasks.append(asyncio.create_task(a))
    else: a.close()
  def add_worker(self, a: Coroutine[Any, Any, Any]):
    """
    Runs a background worker, which may be cancelled at any time. Only runs when the session is persistent.
    args:
      a: Coroutine - the coroutine that should be run
    """
    if self.context.config.persistent:
      self._worker_tasks.append(asyncio.create_task(a))
    else: a.close()

  async def lc_init(self, context: Context) -> None:
    self.context = context
    await to_awaitable(self.on_init)

  async def lc_render(self) -> Element:
    await to_awaitable(self.on_before_update)
    el = await to_awaitable(self.render)
    try: self.context.execution.pending_updates.remove(self.context.id) # NOTE: remove any update that was requested during render
    except KeyError: pass
    await to_awaitable(self.on_after_update)
    return el
  async def lc_destroy(self) -> None:
    await to_awaitable(self.on_before_destroy)
    if len(self._job_tasks) > 0:
      try: _ = await asyncio.wait(self._job_tasks)
      except asyncio.CancelledError: pass
      self._job_tasks.clear()
    if len(self._worker_tasks) > 0:
      for t in self._worker_tasks: _ = t.cancel()
      try: _ = await asyncio.wait(self._worker_tasks)
      except asyncio.CancelledError: pass
      self._worker_tasks.clear()
    await to_awaitable(self.on_after_destroy)

  # async def lc_handle_event(self, event: dict[str, int | float | str | bool | None]):
  #   handler_name = event.pop("$handler_name", None)
  #   if isinstance(handler_name, str):
  #     fn = getattr(self, handler_name, None) # NOTE: this is risky!!
  #     if isinstance(fn, EventHandler):
  #       await to_awaitable(cast(EventHandler[..., Any], fn), **event)

  def on_init(self) -> None | Awaitable[None]: ...
  def on_before_update(self) -> None | Awaitable[None]: ...
  def on_after_update(self) -> None | Awaitable[None]: ...
  def on_before_destroy(self) -> None | Awaitable[None]: ...
  def on_after_destroy(self) -> None | Awaitable[None]: ...

  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: ...

  def tonode(self, context: Context) -> 'Node': return ComponentNode(context, self)

class ComponentNode(Node):
  def __init__(self, context: Context, element: Component) -> None:
    super().__init__(context, ())
    self.element = element

  async def expand(self):
    if len(self.children) > 0:
      raise ValueError("Can not expand already expanded element!")

    await self.element.lc_init(self.context)
    await self._render_inner()

  async def update(self):
    for c in self.children: await c.destroy()
    self.children = ()
    await self._render_inner()

  async def destroy(self):
    for c in self.children: await c.destroy()
    self.children = ()

    await self.element.lc_destroy()

  async def _render_inner(self):
    inner = await self.element.lc_render()
    if self.context.config.render_meta:
      inner = meta_element(self.context.sid, inner)
    self.children = (inner.tonode(self.context.sub("inner")),)
    await self.children[0].expand()
