from rxxxt import Component, event_handler, El, Element, App
import uvicorn

class Counter(Component):
  @property
  def count(self):
    try: return int(self.context.cookies.get("count", 0))
    except: return 0

  @event_handler()
  def on_click(self):
    self.context.set_cookie("count", str(self.count + 1))

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
uvicorn.run(app)
