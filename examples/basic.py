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

  @event_handler(throttle=1000)
  def on_input(self, value: Annotated[str | None, "target.value"]):
    self.context.set_cookie("hello", "world", http_only=True)
    self.state.text = value

  @event_handler()
  def on_navigate(self): self.context.navigate("/page2")

  def render(self) -> Element:
    return El.div(content=[
      El.div(onclick=self.on_click, content=[ f"Count: {self.state.count}" ]),
      El.div(content=[
        El.b(content=[self.state.text])
      ]),
      VEl.input(oninput=self.on_input, value=self.state.text),
      El.button(content=["nav"], onclick=self.on_navigate)
    ])

class ExamplePage2(Component):
  def render(self) -> Element: return El.h1(content=[ "Hello World!" ])

app = App()

app.add_route("/", Example)
app.add_route("/page2", ExamplePage2)

uvicorn.run(app)
