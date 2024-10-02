import uvicorn
from rxxxt import App
from rxxxt.component import Component, event_handler
from rxxxt.elements import El, Element
from rxxxt.state import state_field

class Counter(Component):
  count: int = state_field(default_value=0)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App()
app.add_route("/", Counter)

uvicorn.run(app)
