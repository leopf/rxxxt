from fastapi import FastAPI, Response
import uvicorn
from rxxxt import local_state, Component, event_handler, El, Element, App, PageBuilder, VEl

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

server = FastAPI()

@server.get("/main.css")
def get_css(): return Response("body { margin: 0; font-family: sans-serif; }", media_type="text/css")

page_builder = PageBuilder()
page_builder.add_header(VEl.link(rel="stylesheet", href="/main.css"))

app = App(Counter, page_layout=page_builder)
server.mount("/", app)
uvicorn.run(server)
