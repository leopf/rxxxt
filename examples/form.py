from typing import Annotated
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)

from rxxxt import Component, event_handler, VEl, El, Element, PageBuilder, Page, App

class Form(Component):
  @event_handler(prevent_default=True)
  def on_submit(self, username: Annotated[str, "target.elements.0.value"], password: Annotated[str, "target.elements.1.value"]):
    print(username, password)
    if username == "Hello" and password == "World":
      self.context.navigate("/hello")

  def render(self) -> Element:
    return El.form(onsubmit=self.on_submit, content=[
        El.label(content=["Username"]),
        VEl.input(name="username"),
        El.label(content=["Password"]),
        VEl.input(name="password", type="password"),
        VEl.input(type="submit", value="login")
    ])

page_builder = PageBuilder(Page)
page_builder.add_header(El.style(content=["form * { display: block; }"]))

app = App(page_layout=page_builder, app_data={ "title": "Form" })

app.add_route("/", Form)
app.add_route("/hello", lambda: El.h1(content=[ "Welcome!" ]))

uvicorn.run(app)
