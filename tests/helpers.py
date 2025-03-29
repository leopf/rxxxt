import asyncio
from io import StringIO
from rxxxt.elements import Element
from rxxxt.execution import Context, ContextConfig, State
from rxxxt.node import Node

def element_to_node(el: Element):
  state = State(asyncio.Event())
  context = Context(state, ContextConfig(persistent=False, render_meta=False), ("root",))
  return el.tonode(context)

def render_node(node: Node):
  io = StringIO()
  node.write(io)
  return io.getvalue()

async def render_element(el: Element):
  node = element_to_node(el)
  await node.expand()
  s = render_node(node)
  await node.destroy()
  return s
