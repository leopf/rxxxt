from typing import Annotated
import uvicorn
from rxxxt import App, Component, Element, El, HTMLFragment, event_handler, window_event, query_selector_all_event


class GlobalEvents(Component):
  @event_handler()
  def on_key_press(self, key: Annotated[str, "key"]):
    print("key pressed", key)

  @event_handler()
  def on_hello_world(self, text: Annotated[str, "currentTarget.textContent"]):
    if text and text.strip() == "Hello World":
      print("Hello World paragraph clicked")

  def render(self) -> Element:
    return HTMLFragment([
      window_event("keydown", self.on_key_press),
      query_selector_all_event("click", "p", self.on_hello_world),
      El.p(content=["Hello World"]),
      El.p(content=["Hello Universe"]),
    ])


app = App(GlobalEvents)
uvicorn.run(app)
