from rxxxt import Component, event_handler, VEl, Element, App, local_state
from typing import Annotated
import uvicorn

class Main(Component):
  text = local_state(str)

  @event_handler(throttle=500, debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text = value

  async def on_init(self) -> None:
    if self.text == "":
      self.text = "hello"

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, value=self.text)

app = App(Main)
uvicorn.run(app)
