import uvicorn
from rxxxt import Component, event_handler, El, Element, App, Router
import logging

logging.basicConfig(level=logging.DEBUG)

class Counter(Component):
  @event_handler()
  def on_click(self): print("HELLO")

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {0}"])

router = Router()
router.add_route("/", Counter)

app = App(router)
uvicorn.run(app)
