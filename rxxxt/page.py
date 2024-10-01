from typing import Protocol
from rxxxt.component import Component
from rxxxt.elements import El, Element, HTMLFragment, VEl

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
      El.title(content=[self.context.app_data.get("title", "Document")])
    ])

class PageBuilder(PageFactory):
  def __init__(self, page_factory: PageFactory) -> None:
    self._header_elements: list[Element] = []
    self._body_end_elements: list[Element] = []
    self._page_factory = page_factory

  def add_header(self, el: Element): self._header_elements.append(el)
  def add_body_end(self, el: Element): self._body_end_elements.append(el)

  def __call__(self, header: Element, content: Element, body_end: Element) -> Element:
    return self._page_factory(HTMLFragment([ header, *self._header_elements ]), content, HTMLFragment([ *self._body_end_elements, body_end ]))
