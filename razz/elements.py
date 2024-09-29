from abc import ABC, abstractmethod
import html
from types import NoneType
from typing import TYPE_CHECKING, Callable, Union

if TYPE_CHECKING:
    from razz.execution import Context

class CustomAttribute(ABC):
  @abstractmethod
  def get_html_attribute_key_value(self, original_key: str) -> str: pass

class Element(ABC):
  @abstractmethod
  async def to_html(self, context: 'Context') -> str: pass

class UnescapedHTMLElement(Element):
  def __init__(self, text: str) -> NoneType:
    super().__init__()
    self.text = text
  async def to_html(self, context: 'Context') -> str: return self.text

class HTMLFragment(Element):
  def __init__(self, content: list[Union[Element, str]], key: str | None = None) -> None:
    super().__init__()
    self.key = key
    self.content = content

  async def to_html(self, context: 'Context') -> str:
    if self.key is not None:
      context = context.sub(self.key)

    parts: list[str] = []
    for item in self.content:
      if isinstance(item, Element): parts.append(await item.to_html(context))
      else: parts.append(html.escape(str(item), quote=False))

    return "".join(parts)

class HTMLBaseElement(Element):
  def __init__(self, tag: str, attributes: dict[str, str | CustomAttribute | NoneType]) -> None:
    super().__init__()
    self.tag = tag
    self.attributes = attributes

  def _render_attributes(self):
    parts: list[str] = []
    for k, v in self.attributes.items():
      if isinstance(v, CustomAttribute): k, v = v.get_html_attribute_key_value(k)
      k = html.escape(str(k))
      if v is not None: v = html.escape(str(v))
      if v is None: parts.append(f" {k}")
      else: parts.append(f" {k}=\"{v}\"")
    return "".join(parts)

class HTMLVoidElement(HTMLBaseElement):
  async def to_html(self, context: 'Context') -> str:
    return f"<{html.escape(self.tag)}{self._render_attributes()}>"

class HTMLElement(HTMLBaseElement):
  def __init__(self, tag: str, attributes: dict[str, str | CustomAttribute | NoneType] = {}, content: list[Union[Element, str]] = [], key: str | None = None) -> None:
    super().__init__(tag, attributes)
    self.key = key
    self.content = content

  async def to_html(self, context: 'Context') -> str:
    if self.key is not None:
      context = context.sub(self.key)

    parts: list[str] = []
    for item in self.content:
      if isinstance(item, Element): parts.append(await item.to_html(context))
      else: parts.append(html.escape(str(item), quote=False))

    inner_html = "".join(parts)
    tag = html.escape(self.tag)
    return f"<{tag}{self._render_attributes()}>{inner_html}</{tag}>"

ElementFactory = Callable[[], Element]
