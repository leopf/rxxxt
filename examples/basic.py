from typing import Annotated
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)

from razz import App
from razz.component import Component, event_handler
from razz.elements import Element, HTMLElement, HTMLVoidElement
from razz.state import State

class ExampleState(State):
  count: int = 0
  text: str = ""

class Example(Component):
  state: ExampleState
  
  @event_handler()
  def on_click(self):
    self.state.count += 1
  
  @event_handler()
  def on_input(self, value: Annotated[str, "target.value"]):
    self.state.text = value
  
  def render(self) -> Element:
    return HTMLElement("div", content=[
      HTMLElement("div", attributes={ "onclick": self.on_click }, content=[ f"Count: {self.state.count}" ]),
      HTMLElement("div", content=[
        HTMLElement("b", content=[self.state.text])
      ]),
      HTMLVoidElement("input", attributes={ "onchange": self.on_input, "value": self.state.text })
    ])

app = App(b"SECRET")

app.add_route("/", Example)

uvicorn.run(app)