import asyncio
import unittest
from io import StringIO
from typing import Annotated
from rxxxt.component import Component, event_handler
from rxxxt.elements import Element, El, HTMLFragment, VEl
from rxxxt.events import ContextInputEvent
from rxxxt.execution import Context, ContextConfig, State
from rxxxt.node import Node
from rxxxt.state import local_state
from rxxxt.utils import class_map
from tests.helpers import render_element

class TestElements(unittest.IsolatedAsyncioTestCase):
  async def test_div(self):
    text = await render_element(El.div(content=["Hello World!"]))
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
  unittest.main()
