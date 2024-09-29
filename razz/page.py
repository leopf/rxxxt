from typing import Callable
from razz.component import Component
from razz.elements import Element, HTMLElement, HTMLFragment, HTMLVoidElement

PageFactory = Callable[[Element, Element], Element]

class Page(Component):
  def __init__(self, content_element: Element, script_element: Element) -> None:
    super().__init__()
    self.content_element = content_element
    self.script_element = script_element

  def render(self) -> Element:
    return HTMLFragment([
      HTMLVoidElement("!DOCTYPE", attributes={ "html": None }),
      HTMLElement("html", attributes={ "lang": "en" }, content=[
        HTMLElement("head", content=[
          self.render_headers(),
        ]),
        HTMLElement("body", content=[
          self.render_body(),
          self.script_element
        ])
      ])
    ])

  def render_body(self) -> Element:
    return HTMLElement("div", attributes={ "id": "root" }, content=[ self.content_element ])

  def render_headers(self) -> Element:
    return HTMLFragment([
      HTMLVoidElement("meta", attributes={ "charset": "UTF-8" }),
      HTMLVoidElement("meta", attributes={ "name": "viewport", "content": "width=device-width, initial-scale=1.0" }),
      HTMLElement("title", content=["Document"])
    ])
