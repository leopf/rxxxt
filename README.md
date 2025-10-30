# rxxxt (R-3-X-T)
Server side rendered, reactive web applications in python.

**1 dependency (pydantic).**

## [Documentation](https://leopf.github.io/rxxxt/)
- [App](https://leopf.github.io/rxxxt/app/)
- [Elements](https://leopf.github.io/rxxxt/elements/)
- [Component](https://leopf.github.io/rxxxt/component/)
- [State](https://leopf.github.io/rxxxt/state/)

## Installation

```bash
pip install rxxxt
```

If you want to run the application, you will have to install an ASGI web server like uvicorn as well:
```bash
pip install rxxxt uvicorn
```

## Usage
```python
import uvicorn
from rxxxt import Component, event_handler, El, Element, App, local_state

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
uvicorn.run(app)
```

## Usage with FastAPI
```python
import uvicorn
from fastapi import FastAPI, Response
from rxxxt import local_state, Component, event_handler, El, Element, App, PageBuilder, VEl

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

server = FastAPI()

@server.get("/main.css")
def get_css():
  return Response("body { margin: 0; font-family: sans-serif; }", media_type="text/css")

page_builder = PageBuilder()
page_builder.add_header(VEl.link(rel="stylesheet", href="/main.css"))

app = App(Counter, page_factory=page_builder)
server.mount("/", app)
uvicorn.run(server)
```
