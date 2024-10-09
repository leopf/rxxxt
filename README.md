# rxxxt
Server side rendered, reactive web applications with python.

**1 dependency (pydantic).**

## Usage
```python
import uvicorn
from rxxxt import state_field, Component, event_handler, El, Element, App

class Counter(Component):
  count: int = state_field(default_value=0)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App()
app.add_route("/", Counter)

uvicorn.run(app)
```

## Usage with FastAPI
```python
from fastapi import FastAPI, Response
import uvicorn
from rxxxt import state_field, Component, event_handler, El, Element, App, PageBuilder, Page, VEl

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

app = App(page_layout=page_builder)
app.add_route("/", Counter)

server.mount("/", app)
uvicorn.run(server)
```