import unittest
from typing import Annotated
from rxxxt.component import Component, event_handler
from rxxxt.elements import El
from rxxxt.events import ContextInputEvent
from rxxxt.state import local_state
from tests.helpers import element_to_node, render_node


class TestComponents(unittest.IsolatedAsyncioTestCase):
  class TestCompCounter(Component):
    counter = local_state(int)

    @event_handler()
    def add(self, value: Annotated[int, "target.value"]):
      self.counter += value

    def render(self):
      return El.div(content=[f"c{self.counter}"])

  async def test_component(self):
    comp = TestComponents.TestCompCounter()
    node = element_to_node(comp)
    await node.expand()
    self.assertEqual(render_node(node), "<div>c0</div>")
    comp.counter = 1
    await node.update()
    self.assertEqual(render_node(node), "<div>c1</div>")
    await node.destroy()

  async def test_event_add(self):
     comp = TestComponents.TestCompCounter()
     node = element_to_node(comp)
     await node.expand()
     self.assertEqual(render_node(node), "<div>c0</div>")

     await node.handle_events((ContextInputEvent(context_id=node.context.sid, data={ "$handler_name": "add", "value": 5 }),))
     await node.update()
     self.assertEqual(render_node(node), "<div>c5</div>")
     await node.destroy()

  async def test_double_expand(self):
    el = TestComponents.TestCompCounter()
    node = element_to_node(el)
    await node.expand()
    with self.assertRaises(Exception):
      await node.expand()

if __name__ == "__main__":
  _ = unittest.main()
