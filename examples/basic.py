from typing import Annotated
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)

from razz import App
from razz.component import Component, event_handler
from razz.elements import El, Element, VEl
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
    return El.div(content=[
      El.div(onclick= self.on_click, content=[ f"Count: {self.state.count}" ]),
      El.div(content=[
        El.b(content=[self.state.text])
      ]),
      VEl.input(onchange=self.on_input, value=self.state.text)
    ])

app = App(b"SECRET")

app.add_route("/", Example)

uvicorn.run(app)
