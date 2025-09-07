from rxxxt import Router, router_params, Component, event_handler, El, Element, App
import uvicorn

class ShowPath(Component):
  params = router_params()

  @event_handler()
  def nav_hello(self): self.context.navigate("/hello")

  @event_handler()
  def nav_world(self): self.context.navigate("/world")

  @event_handler()
  def go_to_main(self): self.context.navigate("/")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"Word: {self.params.get('word', '-')}"]),
      El.button(onclick=self.nav_hello, content=["nav 'hello'"]),
      El.button(onclick=self.nav_world, content=["nav 'world'"]),
      El.button(onclick=self.go_to_main, content=["go to main"]),
    ])

class Main(Component):
  @event_handler()
  def go_to_child(self):
    self.context.navigate("/child")

  def render(self):
    return El.div(onclick=self.go_to_child, content=["go to child"])

router = Router()
router.add_route("/", Main)
router.add_route("/{word}", ShowPath)

app = App(router)
uvicorn.run(app)
