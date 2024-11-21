import uvicorn
from rxxxt import state_field, Component, event_handler, El, Element, App, Router

class Counter(Component):
  count: int = state_field(default_value=0)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

router = Router()
router.add_route("/", Counter)

app = App(router)
uvicorn.run(app)
