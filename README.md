# rxxxt (R-3-X-T)
Server side rendered, reactive web applications in python.

**1 dependency (pydantic).**

## [Documentation](https://leopf.github.io/rxxxt/)
- [App](https://leopf.github.io/rxxxt/app/) - the app
- [Elements](https://leopf.github.io/rxxxt/elements/) - creating html elements
- [Component](https://leopf.github.io/rxxxt/component/) - defining components
- [State](https://leopf.github.io/rxxxt/state/) - how state works

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
from rxxxt import Component, event_handler, El, Element, App, local_state
import uvicorn

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
uvicorn.run(app)
```

## Usage with FastAPI
```python
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

app = App(Counter, page_factory=page_builder)
server.mount("/", app)
uvicorn.run(server)
```
