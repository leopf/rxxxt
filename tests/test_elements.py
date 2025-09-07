import unittest
from rxxxt.component import Component
from rxxxt.elements import El, HTMLFragment, LazyElement, VEl
from rxxxt.execution import Context
from rxxxt.utils import class_map
from tests.helpers import render_element

class TestElements(unittest.IsolatedAsyncioTestCase):
  async def test_div(self):
    text = await render_element(El.div(content=["Hello World!"]))
    self.assertEqual(text, "<div>Hello World!</div>")

  async def test_lazy_div(self):
    @LazyElement
    def LazyDiv(_: Context): return El.div(content=["Hello World!"])
    text = await render_element(LazyDiv)
    self.assertEqual(text, "<div>Hello World!</div>")

  async def test_input(self):
    text = await render_element(VEl.input(type="text"))
    self.assertEqual(text, "<input type=\"text\">")

  async def test_fragment(self):
    text = await render_element(HTMLFragment([
      El.div(content=["Hello"]),
      El.div(content=["World"])
    ]))
    self.assertEqual(text, "<div>Hello</div><div>World</div>")

  async def test_class_map(self):
    text = await render_element(VEl.input(_class=class_map({ "text-input": True })))
    self.assertEqual(text, "<input class=\"text-input\">")

    text = await render_element(VEl.input(_class=class_map({ "text-input": False })))
    self.assertEqual(text, "<input class=\"\">")

  async def test_component(self):
    class TestComp(Component):
      def render(self):
        return El.div(content=["Hello World!"])

    text = await render_element(TestComp())
    self.assertEqual(text, "<div>Hello World!</div>")

if __name__ == "__main__":
  _ = unittest.main()
