import uvicorn
from rxxxt import Component, event_handler, El, Element, App, Router, local_state

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

router = Router()
router.add_route("/", Counter)

app = App(router)
uvicorn.run(app)
