import asyncio
from io import StringIO
from typing import Any
from rxxxt.elements import Element
from rxxxt.execution import Context, ContextConfig, Execution
from rxxxt.newstate import State
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
