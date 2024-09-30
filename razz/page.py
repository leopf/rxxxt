from typing import Callable
from razz.component import Component
from razz.elements import El, Element, HTMLFragment, VEl

PageFactory = Callable[[Element, Element], Element]

class Page(Component):
  def __init__(self, content_element: Element, script_element: Element) -> None:
    super().__init__()
    self.content_element = content_element
    self.script_element = script_element

  def render(self) -> Element:
    return HTMLFragment([
      VEl["!DOCTYPE"](html=None),
      El.html(content=[
        El.head(content=[ self.render_headers() ]),
        El.body(content=[
          self.render_body(),
          self.script_element
        ])
      ])
    ])

  def render_body(self) -> Element:
    return El.div(id="razz-root", content=[ self.content_element ])

  def render_headers(self) -> Element:
    return HTMLFragment([
      VEl.meta(charset="UTF-8"),
      VEl.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
      El.title(content=["Document"])
    ])
