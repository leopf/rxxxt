import unittest
from typing import Annotated
from rxxxt.component import Component, event_handler
from rxxxt.elements import El, WithRegistered
from rxxxt.events import ContextInputEvent
from rxxxt.state import local_state
from tests.helpers import element_to_node, render_node


class TestComponents(unittest.IsolatedAsyncioTestCase):
  class Counter(Component):
    counter = local_state(int)

    @event_handler()
    def add(self, value: Annotated[int, "target.value"]):
      self.counter += value

    def render(self):
      return El.div(content=[f"c{self.counter}"])

  class RegistryComp(Component):
    def render(self):
      return El.div(content=[self.context.registered("header", str)])

  async def test_registry(self):
    comp = TestComponents.RegistryComp()
    with self.assertRaises(TypeError):
      node = element_to_node(comp, {})
      await node.expand()

    node = element_to_node(comp, { "header": "1337" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>1337</div>")

  async def test_with_registered(self):
    comp = WithRegistered({ "header": "deadbeef" }, TestComponents.RegistryComp())
    node = element_to_node(comp, {})
    await node.expand()
    self.assertEqual(render_node(node), "<div>deadbeef</div>")

    node = element_to_node(comp, { "header": "1337" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>deadbeef</div>")

  async def test_component(self):
    comp = TestComponents.Counter()
    node = element_to_node(comp)
    await node.expand()
    self.assertEqual(render_node(node), "<div>c0</div>")
    comp.counter = 1
    await node.update()
    self.assertEqual(render_node(node), "<div>c1</div>")
    await node.destroy()

  async def test_event_add(self):
     comp = TestComponents.Counter()
     node = element_to_node(comp)
     await node.expand()
     self.assertEqual(render_node(node), "<div>c0</div>")

     await node.handle_events((ContextInputEvent(context_id=node.context.sid, data={ "$handler_name": "add", "value": 5 }),))
     await node.update()
     self.assertEqual(render_node(node), "<div>c5</div>")
     await node.destroy()

  async def test_double_expand(self):
    el = TestComponents.Counter()
    node = element_to_node(el)
    await node.expand()
    with self.assertRaises(Exception):
      await node.expand()

if __name__ == "__main__":
  _ = unittest.main()
