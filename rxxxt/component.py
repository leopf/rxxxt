from abc import abstractmethod
import asyncio
import base64
import inspect
from typing import Annotated, Any, Callable, Coroutine, Generic, ParamSpec, TypeVar, get_args, get_origin
from pydantic import validate_call
from typing_extensions import Awaitable
from rxxxt.elements import CustomAttribute, Element, meta_element
from rxxxt.events import ContextInputEventDescriptor, ContextInputEventDescriptorGenerator, ContextInputEventHandlerOptions, InputEvent
from rxxxt.execution import Context
from rxxxt.helpers import to_awaitable
from rxxxt.node import Node

EHP = ParamSpec('EHP')
EHR = TypeVar('EHR')

class ClassEventHandler(Generic[EHP, EHR]):
  def __init__(self, fn:  Callable[EHP, EHR], options: ContextInputEventHandlerOptions) -> None:
    self.fn = fn
    self.options = options
  def __get__(self, instance, owner): return InstanceEventHandler(self.fn, self.options, instance)
  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: raise RuntimeError("The event handler can only be called when attached to an instance!")

class InstanceEventHandler(ClassEventHandler, Generic[EHP, EHR], CustomAttribute, ContextInputEventDescriptorGenerator):
  def __init__(self, fn: Callable[EHP, EHR], options: ContextInputEventHandlerOptions, instance: Any) -> None:
    super().__init__(validate_call(fn), options)
    if not isinstance(instance, Component): raise ValueError("The provided instance must be a component!")
    self.instance = instance

  @property
  def descriptor(self):
    return ContextInputEventDescriptor(
      context_id=self.instance.context.sid,
      handler_name=self.fn.__name__,
      param_map=self._get_param_map(),
      options=self.options)

  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: return self.fn(self.instance, *args, **kwargs)

  def get_key_value(self, original_key: str):
    if not original_key.startswith("on"): raise ValueError("Event handler must be applied to an attribute starting with 'on'.")
    v = base64.b64encode(self.descriptor.model_dump_json(exclude_defaults=True).encode("utf-8")).decode("utf-8")
    return (f"rxxxt-on-{original_key[2:]}", v)

  def _get_param_map(self):
    param_map: dict[str, str] = {}
    sig = inspect.signature(self.fn)

    for i, (name, param) in enumerate(sig.parameters.items()):
      if i == 0: continue # skip self

      if get_origin(param.annotation) is Annotated:
        args = get_args(param.annotation)
        metadata = args[1:]

        if len(metadata) < 1:
          raise ValueError(f"Parameter '{name}' is missing the second annotation.")

        param_map[name] = metadata[0]
      else:
        raise TypeError(f"Parameter '{name}' must be of type Annotated.")

    return param_map

def event_handler(**kwargs):
  options = ContextInputEventHandlerOptions.model_validate(kwargs)
  def _inner(fn) -> ClassEventHandler: return ClassEventHandler(fn, options)
  return _inner

class HandleNavigate(CustomAttribute):
  def __init__(self, location: str) -> None:
    super().__init__()
    self.location = location

  def get_key_value(self, original_key: str) -> tuple[str, str]:
    return (original_key, f"window.rxxxt.navigate('{self.location}');")

class Component(Element):
  def __init__(self) -> None:
    super().__init__()
    self.context: Context
    self._worker_tasks: list[asyncio.Task] = []
    self._job_tasks: list[asyncio.Task] = []

  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: ...

  def add_job(self, a: Coroutine):
    """
    Runs a background job until completion. Only runs when the session is persistent.
    args:
      a: Coroutine - the coroutine that should be run
    """
    if self.context.config.persistent:
      self._worker_tasks.append(asyncio.create_task(a))
    else: a.close()
  def add_worker(self, a: Coroutine):
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
    await self.on_init()

  async def lc_render(self) -> Element:
    await self.on_before_update()
    el = await to_awaitable(self.render)
    await self.on_after_update()
    return el
  async def lc_destroy(self) -> None:
    await self.on_before_destroy()
    if len(self._job_tasks) > 0:
      try: await asyncio.wait(self._job_tasks)
      except asyncio.CancelledError: pass
      self._job_tasks.clear()
    if len(self._worker_tasks) > 0:
      for t in self._worker_tasks: t.cancel()
      try: await asyncio.wait(self._worker_tasks)
      except asyncio.CancelledError: pass
      self._worker_tasks.clear()
    await self.on_after_destroy()

  async def lc_handle_event(self, event: dict[str, int | float | str | bool]):
    handler_name = event.pop("$handler_name", None)
    if isinstance(handler_name, str):
      handler = getattr(self, handler_name, None) # NOTE: this is risky!!
      if isinstance(handler, InstanceEventHandler):
        await to_awaitable(handler, **event)

  async def on_init(self) -> None: ...
  async def on_before_update(self) -> None: ...
  async def on_after_update(self) -> None: ...
  async def on_before_destroy(self) -> None: ...
  async def on_after_destroy(self) -> None: ...

  def tonode(self, context: Context) -> 'Node': return ComponentNode(context, self)

class ComponentNode(Node):
  def __init__(self, context: Context, element: Component) -> None:
    super().__init__(context, [])
    self.element = element

  async def expand(self):
    if len(self.children) > 0:
      raise ValueError("Can not expand already expanded element!")

    await self.element.lc_init(self.context)
    await self._render_inner()

  async def update(self):
    for c in self.children: await c.destroy()
    self.children.clear()
    await self._render_inner()

  async def handle_events(self, events: list[InputEvent]):
    for e in events:
      if self.context.sid == e.context_id:
        await self.element.lc_handle_event(dict(e.data))
    await super().handle_events(events)

  async def destroy(self):
    for c in self.children: await c.destroy()
    self.children.clear()

    await self.element.lc_destroy()
    self.context.unsubscribe_all()

  async def _render_inner(self):
    inner = await self.element.lc_render()
    if self.context.config.render_meta:
      inner = meta_element(self.context.sid, inner)
    self.children.append(inner.tonode(self.context.sub("inner")))
    await self.children[0].expand()
