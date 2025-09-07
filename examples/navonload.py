from rxxxt import Component, El, App
from rxxxt.router import Router
import uvicorn

class Main(Component):
  async def render(self):
    self.context.navigate("/login")
    return El.div(content=["nav"])

router = Router()
router.add_route("/login", lambda: El.div(["login"]))
router.add_route("/", Main)

app = App(router)
uvicorn.run(app)
