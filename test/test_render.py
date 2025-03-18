import asyncio
from io import StringIO
import unittest

from rxxxt.elements import Element, El
from rxxxt.execution import Context, ContextConfig, State

async def render_element(el: Element):
  state = State(asyncio.Event())
  context = Context(state, ContextConfig(persistent=False, render_meta=False), ("root",))
  node = el.tonode(context)
  await node.expand()
  io = StringIO()
  node.write(io)
  await node.destroy()
  return io.getvalue()

class TestRender(unittest.IsolatedAsyncioTestCase):
  async def test_div(self):
    text = await render_element(El.div(content=["Hello World!"]))
    self.assertEqual(text, "<div>Hello World!</div>")


if __name__ == "__main__":
  unittest.main()
