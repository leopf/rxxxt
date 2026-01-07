# rxxxt (R-3-X-T)
Server side rendered, reactive web applications in python.

**1 dependency (pydantic).**

Features:

- stateless (HTTP) and stateful (websocket) sessions
- server to client updates
- integrated state management
- background workers
- routing and navigation
- partial page updates
- more...

Have a look at the [Getting Started guide](https://leopf.github.io/rxxxt/getting-started/) or check out the [full documentation](https://leopf.github.io/rxxxt/).

## Installation

```bash
pip install rxxxt
```

If you want to run the application, you will have to install an ASGI web server like uvicorn (with `[standard]` to allow for websockets) as well:
```bash
pip install rxxxt uvicorn[standard]
```

## Usage
```python
import uvicorn
from rxxxt import Component, El, Element, App, local_state

class Counter(Component):
  count = local_state(int)

  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
uvicorn.run(app)
```
[result.webm](https://github.com/user-attachments/assets/cbfd61cb-8630-4d3c-87ec-e17cbae3a421)

## Usage with FastAPI
```python
import uvicorn
from fastapi import FastAPI, Response
from rxxxt import local_state, Component, El, Element, App, PageBuilder, VEl

class Counter(Component):
  count = local_state(int)

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

## Notes
- after restarting python, your browser session will stop working (until you refresh), because your old state has been invalidated. Make sure to set `JWT_SECRET` to avoid this.
