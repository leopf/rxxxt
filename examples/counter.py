import asyncio
from rxxxt import Component, El, Element, App, local_state
from rxxxt.httpserver import HTTPServer, ServerConfig

class Counter(Component):
  count = local_state(lambda: 42, int)

  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
server = HTTPServer(app, ServerConfig(host="127.0.0.1", port=8000))
asyncio.run(server.run())
