from rxxxt import Component, event_handler, VEl, Element, App, local_state
from typing import Annotated
import uvicorn

from rxxxt.elements import El, HTMLFragment

class Main(Component):
  text = local_state(str)

  @event_handler(no_trigger=True)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text = value

  @event_handler()
  def on_click(self): pass

  def render(self) -> Element:
    return HTMLFragment([
      VEl.input(oninput=self.on_input, value=self.text),
      El.div(onclick=self.on_click, content=["hello"])
    ])

app = App(Main)
uvicorn.run(app)
