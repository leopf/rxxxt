from rxxxt import Router, router_params, Component, event_handler, El, Element, App
import uvicorn

class ShowPath(Component):
  params = router_params()

  @event_handler()
  def nav_path1(self): self.context.navigate("/path1")

  @event_handler()
  def nav_path2(self): self.context.navigate("/path2")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"Path: {self.params.get('path', '-')}"]),
      El.button(onclick=self.nav_path1, content=["nav path 1"]),
      El.button(onclick=self.nav_path2, content=["nav path 2"]),
    ])

router = Router()
router.add_route("/{path}", ShowPath)

app = App(router)
uvicorn.run(app)
