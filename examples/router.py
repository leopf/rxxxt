from rxxxt import Router, router_params, Component, event_handler, El, Element, App
import uvicorn

class ShowPath(Component):
  params = router_params()

  @event_handler()
  def nav_hello(self): self.context.navigate("/hello")

  @event_handler()
  def nav_world(self): self.context.navigate("/world")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"Word: {self.params.get('word', '-')}"]),
      El.button(onclick=self.nav_hello, content=["nav 'hello'"]),
      El.button(onclick=self.nav_world, content=["nav 'world'"]),
    ])

router = Router()
router.add_route("/{word}", ShowPath)

app = App(router)
uvicorn.run(app)
