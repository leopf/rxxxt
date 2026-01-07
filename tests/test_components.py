import unittest
from typing import Annotated
from rxxxt.component import Component, SharedExternalState, event_handler, local_state
from rxxxt.elements import El, WithRegistered
from tests.helpers import element_to_node, render_node

class TestComponents(unittest.IsolatedAsyncioTestCase):
  class Counter(Component):
    counter = local_state(int)

    def add(self, value: Annotated[int, "target.value"]):
      self.counter += value

    def render(self):
      return El.div(content=[f"c{self.counter}"])

  class Button(Component):
    @event_handler()
    def on_click(self): ...
    def render(self):
      return El.div(onclick=self.on_click, content=["click"])

  class PlainButton(Component):
    def on_click(self): ...
    def render(self):
      return El.div(onclick=self.on_click, content=["plain"])

  class RegistryComp(Component):
    def render(self):
      return El.div(content=[self.context.registered("header", str)])

  async def test_render_event_handler(self):
    comp = TestComponents.Button()
    node = element_to_node(comp)
    await node.expand()
    self.assertIn("rxxxt-on-click", render_node(node))

  async def test_plain_event_handler_without_decorator(self):
    comp = TestComponents.PlainButton()
    node = element_to_node(comp)
    await node.expand()
    self.assertIn("rxxxt-on-click", render_node(node))

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

     comp.add(5)
     await node.update()
     self.assertEqual(render_node(node), "<div>c5</div>")
     await node.destroy()

  async def test_double_expand(self):
    el = TestComponents.Counter()
    node = element_to_node(el)
    await node.expand()
    with self.assertRaises(Exception):
      await node.expand()

  async def test_shared_external_state(self):
    class Subscriber(Component):
      shared = SharedExternalState[dict[str, int]]({ "count": 10 })
      def render(self):
        _ = self.shared  # trigger registration
        return El.div(content=[f"shared:{self.shared.value['count']}"])

    node_a = element_to_node(Subscriber())
    await node_a.expand()
    node_b = element_to_node(Subscriber())
    await node_b.expand()
    self.assertEqual(render_node(node_a), "<div>shared:10</div>")

    Subscriber.shared.value = { "count": 1337 }
    await node_a.update()
    await node_b.update()
    self.assertEqual(render_node(node_a), "<div>shared:1337</div>")
    self.assertEqual(render_node(node_b), "<div>shared:1337</div>")

    Subscriber.shared.value["count"] = 7331
    Subscriber.shared.update()
    await node_a.update()
    await node_b.update()
    self.assertEqual(render_node(node_a), "<div>shared:7331</div>")
    self.assertEqual(render_node(node_b), "<div>shared:7331</div>")

    class NotAComponent:
      shared = Subscriber.shared
    with self.assertRaises(TypeError):
      _ = NotAComponent().shared

    await node_a.destroy()
    await node_b.destroy()

if __name__ == "__main__":
  _ = unittest.main()
