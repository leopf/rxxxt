from typing import Protocol
from razz.component import Component
from razz.elements import El, Element, HTMLFragment, VEl

class PageFactory(Protocol):
  def __call__(self, header: Element, content: Element, body_end: Element) -> Element: ...

class Page(Component):
  def __init__(self, header: Element, content: Element, body_end: Element) -> None:
    super().__init__()
    self.el_header = header
    self.el_content = content
    self.el_body_end = body_end

  def render(self) -> Element:
    return HTMLFragment([
      VEl["!DOCTYPE"](html=None),
      El.html(content=[
        El.head(content=[ self.render_headers(), self.el_header ]),
        El.body(content=[
          self.render_body(),
          self.el_body_end
        ])
      ])
    ])

  def render_body(self) -> Element: return self.el_content
  def render_headers(self) -> Element:
    return HTMLFragment([
      VEl.meta(charset="UTF-8"),
      VEl.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
      El.title(content=["Document"])
    ])
