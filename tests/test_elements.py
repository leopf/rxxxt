import unittest, html
from rxxxt.component import Component
from rxxxt.elements import El, HTMLFragment, VEl, lazy_element, class_map
from rxxxt.execution import Context
from tests.helpers import render_element

class TestElements(unittest.IsolatedAsyncioTestCase):
  async def test_div(self):
    text = await render_element(El.div(content=["Hello World!"]))
    self.assertEqual(text, "<div>Hello World!</div>")

  async def test_lazy_div(self):
    @lazy_element
    def LazyDiv(context: Context, number: int):
      return El.div(content=[f"Hello World {number + context.registered('somevalue', int)}!"])
    text = await render_element(LazyDiv(number=1337), registry={ "somevalue": 42 })
    self.assertEqual(text, f"<div>Hello World {1337 + 42}!</div>")

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

  async def test_boolean_attribute(self):
    self.assertEqual(await render_element(VEl.input(disabled=True)), "<input disabled>")
    self.assertEqual(await render_element(VEl.input(disabled=False)), "<input>")

  async def test_callable_attribute_value(self):
    async def handler(): ...
    text = await render_element(El.button(onclick=handler, content=["Click"]))
    self.assertIn("rxxxt-on-click", text)

  async def test_component(self):
    class TestComp(Component):
      def render(self):
        return El.div(content=["Hello World!"])

    text = await render_element(TestComp())
    self.assertEqual(text, "<div>Hello World!</div>")

  async def test_attribute_name_is_sanitized(self):
    malicious_name = "\"><script>alert(1)</script>"
    text = await render_element(VEl.input(**{malicious_name: "safe"}))
    self.assertEqual(text, f"<input {html.escape(malicious_name)}=\"safe\">")

  async def test_attribute_value_is_sanitized(self):
    malicious_value = "\" onfocus=\"alert(1) & <script>alert('x')</script>"
    text = await render_element(VEl.input(value=malicious_value))
    self.assertEqual(text, f"<input value=\"{html.escape(malicious_value)}\">")

if __name__ == "__main__":
  _ = unittest.main()
