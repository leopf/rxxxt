from fastapi import FastAPI, Response
import uvicorn
from rxxxt import state_field, Component, event_handler, El, Element, App, PageBuilder, Page, VEl, Router

class Counter(Component):
  count: int = state_field(default_value=0)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

server = FastAPI()

@server.get("/main.css")
def get_css(): return Response("body { margin: 0; font-family: sans-serif; }", media_type="text/css")

page_builder = PageBuilder(Page)
page_builder.add_header(VEl.link(rel="stylesheet", href="/main.css"))

router = Router()
router.add_route("/", Counter)
app = App(router, page_layout=page_builder)

server.mount("/", app)
uvicorn.run(server)
