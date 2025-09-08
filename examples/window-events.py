from rxxxt import Router, router_params, Component, event_handler, El, Element, App
import uvicorn

key_pressed_counter = 0

class Child(Component):
  params = router_params()

  @event_handler()
  def go_to_main(self): self.context.navigate("/")

  @event_handler()
  def on_window_key_press(self):
    global key_pressed_counter
    key_pressed_counter += 1
    print("key pressed", key_pressed_counter)

  def render(self) -> Element:
    self.context.add_window_event("keypress", self.on_window_key_press)
    return El.div(content=[
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
router.add_route("/{path*}", Child)

app = App(router)
uvicorn.run(app)
