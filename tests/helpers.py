import asyncio
from io import StringIO
from typing import Any
from rxxxt.elements import CustomAttribute, Element
from rxxxt.execution import Context, ContextConfig, Execution
from rxxxt.state import State
from rxxxt.node import Node

def element_to_node(el: Element, registry: dict[str, Any] | None = None):
  context_config = ContextConfig(persistent=False, render_meta=False)
  execution = Execution([], set(), asyncio.Event())
  return el.tonode(Context(id=("root",), state=State(), registry=registry or {}, config=context_config, execution=execution))

def render_node(node: Node):
  io = StringIO()
  node.write(io)
  return io.getvalue()

async def render_element(el: Element, registry: dict[str, Any] | None = None):
  node = element_to_node(el, registry)
  await node.expand()
  s = render_node(node)
  await node.destroy()
  return s

class TrackedCustomAttribute:
  class Inner(CustomAttribute):
    def __init__(self, attr: CustomAttribute, outer: 'TrackedCustomAttribute') -> None:
      super().__init__()
      self._outer = outer
      self._attr = attr

    def tonode(self, context: Context, original_key: str) -> Node:
      self._outer.last_context = context
      self._outer.set_event.set()
      return self._attr.tonode(context, original_key)

  def __init__(self) -> None:
    super().__init__()
    self.last_context: Context | None = None
    self.set_event = asyncio.Event()

  def __call__(self, attr: CustomAttribute) -> Any:
    return TrackedCustomAttribute.Inner(attr, self)
