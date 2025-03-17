from abc import abstractmethod
import asyncio
import base64
import inspect
import json
from typing import Annotated, Any, Callable, Coroutine, Generic, ParamSpec, TypeVar, get_args, get_origin
from pydantic import BaseModel, validate_call
from typing_extensions import Awaitable
from rxxxt.elements import CustomAttribute, Element, meta_element
from rxxxt.execution import Context, InputEvent
from rxxxt.helpers import to_awaitable
from rxxxt.node import Node

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
  def __init__(self, fn: Callable[EHP, EHR], options: EventHandlerOptions, instance: Any) -> None:
    super().__init__(validate_call(fn), options)
    if not isinstance(instance, Component): raise ValueError("The provided instance must be a component!")
    self.instance = instance

  def __call__(self, *args: EHP.args, **kwargs: EHP.kwargs) -> EHR: return self.fn(self.instance, *args, **kwargs)

  def get_key_value(self, original_key: str):
    if not original_key.startswith("on"): raise ValueError("Event handler must be applied to an attribute starting with 'on'.")
    if self.instance.context is None: raise ValueError("The instance must have a context_id to create an event value.")
    v = base64.b64encode(json.dumps({
      "context_id": self.instance.context.sid,
      "handler_name": self.fn.__name__,
      "param_map": self._get_param_map(),
      "options": self.options.model_dump(exclude_defaults=True)
    }).encode("utf-8")).decode("utf-8")
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
  options = EventHandlerOptions.model_validate(kwargs)
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
    self._bg_tasks: list[asyncio.Task] = []

  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: ...

  def add_background_task(self, a: Coroutine):
    if not self.context.config.persistent:
      a.close()
      return
    self._bg_tasks.append(asyncio.create_task(a))
  def request_update(self): self.context.request_update()

  async def lc_init(self, context: Context) -> None:
    self.context = context
    await self.on_init()
  async def lc_destroy(self) -> None:
    await self.on_before_destroy()
    if len(self._bg_tasks) > 0:
      for t in self._bg_tasks: t.cancel()
      try: await asyncio.wait(self._bg_tasks)
      except asyncio.CancelledError: pass
      self._bg_tasks.clear()
    await self.on_after_destroy()
  async def lc_handle_event(self, event: dict[str, int | float | str | bool]):
    handler_name = event.pop("$handler_name", None)
    if isinstance(handler_name, str):
      handler = getattr(self, handler_name, None) # NOTE: this is risky!!
      if isinstance(handler, InstanceEventHandler):
        await to_awaitable(handler, **event)

  async def on_init(self) -> None: ...
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
    self.context.unregister()

  async def _render_inner(self):
    inner = await to_awaitable(self.element.render)
    self.children.append(meta_element(self.context.sid, inner).tonode(self.context.sub("inner")))
    await self.children[0].expand()
