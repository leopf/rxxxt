from typing import Protocol
from rxxxt.elements import El, Element, HTMLFragment, VEl
from collections.abc import Iterable

class PageFactory(Protocol):
  def __call__(self, header: Element, content: Element, body_end: Element) -> Element: ...

def default_page(header: Element, content: Element, body_end: Element):
  return HTMLFragment([
    VEl["!DOCTYPE"](html=None),
    El.html(content=[
      El.head(content=[
        VEl.meta(charset="UTF-8"),
        VEl.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        header
      ]),
      El.body(content=[
        content,
        body_end
      ])
    ])
  ])

class PageBuilder(PageFactory):
  def __init__(self, page_factory: PageFactory = default_page) -> None:
    self._header_elements: list[Element] = []
    self._body_end_elements: list[Element] = []
    self._page_factory = page_factory

  def add_stylesheet(self, url: str, **kwargs: str): self.add_header(VEl.link(rel="stylesheet", href=url, **kwargs))
  def add_header_script(self, url: str, content: Iterable[Element | str] = (), **kwargs: str):
    self.add_header(El.script(src=url, content=content, **kwargs))
  def add_body_script(self, url: str, content: Iterable[Element | str] = (), **kwargs: str):
    self.add_body_end(El.script(src=url, content=content, **kwargs))

  def add_header(self, el: Element): self._header_elements.append(el)
  def add_body_end(self, el: Element): self._body_end_elements.append(el)

  def __call__(self, header: Element, content: Element, body_end: Element) -> Element:
    return self._page_factory(HTMLFragment([ header, *self._header_elements ]), content, HTMLFragment([ *self._body_end_elements, body_end ]))
