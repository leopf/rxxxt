from typing import Annotated
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)

from rxxxt import State, Context, Component, event_handler, VEl, El, Element, PageBuilder, Page, App, Router, HandleNavigate

class ExampleState(State):
  count: int = 0
  text: str = ""

  def init(self, context: 'Context'): self.text = context.query_string or ""

class Example(Component):
  state: ExampleState

  @event_handler()
  def on_click(self):
    self.state.count += 1
    self.context.use_websocket(True)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str | None, "target.value"]):
    self.context.set_cookie("hello", "world", http_only=True)
    self.state.text = value or ""

  @event_handler()
  def on_navigate(self): self.context.navigate("/page2")

  @event_handler()
  def on_navigate_google(self): self.context.navigate("https://www.google.com/")

  def render(self) -> Element:
    return El.div(content=[
      El.div(onclick=self.on_click, content=[ f"Count: {self.state.count}" ]),
      El.div(content=[
        El.b(content=[self.state.text])
      ]),
      VEl.input(oninput=self.on_input, value=self.state.text),
      El.button(content=["nav"], onclick=self.on_navigate),
      El.button(content=["nav to google"], onclick=self.on_navigate_google),
      El.button(content=["nav to bing"], onclick=HandleNavigate("https://bing.com")),
    ])

class ExamplePage2(Component):
  def render(self) -> Element: return El.h1(content=[ "Hello World!" ])

page_builder = PageBuilder(Page)
page_builder.add_header(VEl.link(href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap", rel="stylesheet"))
page_builder.add_header(El.style(content=["""
body {
  margin: 0;
  font-family: Roboto;
}
"""]))

router = Router()
router.add_route("/", Example)
router.add_route("/page2", ExamplePage2)

app = App(router, page_layout=page_builder)
uvicorn.run(app)
