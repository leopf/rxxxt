from rxxxt import Component, El, Element, App, local_state
import uvicorn

class Counter(Component):
  count = local_state(int)

  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[
      El.div(content=[f"Count: {self.count}"])
    ])

app = App(Counter)
uvicorn.run(app)
