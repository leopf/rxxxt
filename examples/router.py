from rxxxt import Router, router_params, Component, event_handler, El, Element, App
from rxxxt.component import HandleNavigate
from rxxxt.elements import HTMLFragment
import uvicorn

class ShowPath(Component):
  params = router_params()

  @event_handler()
  def nav_hello(self): self.context.navigate("/hello")

  @event_handler()
  def go_to_main(self): self.context.navigate("/")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"Word: {self.params.get('word', '-')}"]),
      El.button(onclick=self.nav_hello, content=["nav 'hello'"]),
      El.button(onclick=HandleNavigate("/world"), content=["nav 'world'"]),
      El.button(onclick=self.go_to_main, content=["go to main"]),
    ])

class Main(Component):
  @event_handler()
  def go_to_child(self):
    self.context.navigate("/child")

  @event_handler()
  def go_to_full_child(self):
    self.context.navigate("http://127.0.0.1:8000/child")

  @event_handler()
  def go_to_external(self):
    self.context.navigate("https://google.com")

  def render(self):
    return HTMLFragment([
      El.div(onclick=self.go_to_child, content=["go to child"]),
      El.div(onclick=self.go_to_full_child, content=["go to full child"]),
      El.div(onclick=self.go_to_external, content=["go to external"]),
    ])

router = Router()
router.add_route("/", Main)
router.add_route("/{word}", ShowPath)

app = App(router)
uvicorn.run(app)
