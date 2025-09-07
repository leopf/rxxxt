from abc import ABC, abstractmethod
import html
import logging
from typing import Callable, Protocol
from collections.abc import Iterable
from rxxxt.execution import Context
from rxxxt.node import ElementNode, FragmentNode, Node, TextNode, VoidElementNode
from typing import Any

class CustomAttribute(ABC):
  @abstractmethod
  def get_key_value(self, original_key: str) -> tuple[str, str | None]: ...

class Element(ABC):
  @abstractmethod
  def tonode(self, context: Context) -> Node: ...

ElementContent = Iterable[Element | str]
HTMLAttributeValue = str | bool | int | float | CustomAttribute | None

def element_content_to_nodes(context: Context, content: ElementContent):
  nodes: list[Node] = []
  for idx, c in enumerate(content):
    scontext = context.sub(idx)
    if isinstance(c, Element): nodes.append(c.tonode(scontext))
    else: nodes.append(TextNode(scontext, html.escape(c)))
  return tuple(nodes)

class HTMLFragment(Element):
  def __init__(self, content: ElementContent) -> None:
    super().__init__()
    self._content = tuple(content)

  def tonode(self, context: Context) -> Node:
    return FragmentNode(context, element_content_to_nodes(context, self._content))

class HTMLVoidElement(Element):
  def __init__(self, tag: str, attributes: dict[str, HTMLAttributeValue]) -> None:
    super().__init__()
    self._tag = tag
    self._attributes: dict[str, str | None] = {}
    for k, v in attributes.items():
      if isinstance(v, CustomAttribute): k, v = v.get_key_value(k)
      elif isinstance(v, bool):
        if not v: continue
        v = None
      elif isinstance(v, (int, float)): v = str(v)
      self._attributes[k] = v

  def tonode(self, context: Context) -> 'Node':
    return VoidElementNode(context, self._tag, self._attributes)

class HTMLElement(HTMLVoidElement):
  def __init__(self, tag: str, attributes: dict[str, HTMLAttributeValue], content: ElementContent) -> None:
    super().__init__(tag, attributes)
    self._content = tuple(content)

  def tonode(self, context: Context) -> 'Node':
    return ElementNode(context, self._tag, self._attributes, element_content_to_nodes(context, self._content))

class KeyedElement(Element):
  def __init__(self, key: str, element: Element) -> None:
    super().__init__()
    self._key = key
    self._element = element

  def tonode(self, context: Context) -> 'Node':
    try: context = context.replace_index(self._key)
    except ValueError as e: logging.debug(f"Failed to replace index with key {self._key}", e)
    return self._element.tonode(context)

class WithRegistered(Element):
  def __init__(self, register: dict[str, Any], child: Element) -> None:
    super().__init__()
    self._register = register
    self._child = child

  def tonode(self, context: Context) -> 'Node':
    return self._child.tonode(context.update_registry(self._register))

class LazyElement(Element):
  def __init__(self, fn: Callable[[Context], Element]) -> None:
    self._fn = fn

  def tonode(self, context: Context) -> 'Node':
    return self._fn(context).tonode(context)

class UnescapedHTMLElement(Element):
  def __init__(self, text: str) -> None:
    super().__init__()
    self._text = text

  def tonode(self, context: Context) -> 'Node': return TextNode(context, self._text)

class CreateHTMLElement(Protocol):
  def __call__(self, content: Iterable[Element | str] = (), key: str | None = None, **kwargs: HTMLAttributeValue) -> Element: ...

class _El(type):
  def __getitem__(cls, name: str) -> CreateHTMLElement:
    def _inner(content: Iterable[Element | str] = (), key: str | None = None, **kwargs: HTMLAttributeValue):
      el = HTMLElement(name, attributes={ k.lstrip("_"): v for k,v in kwargs.items() }, content=list(content))
      if key is not None: el = KeyedElement(key, el)
      return el
    return _inner
  def __getattribute__(cls, name: str): return cls[name]

class El(metaclass=_El): ...

class CreateHTMLVoidElement(Protocol):
  def __call__(self, key: str | None = None, **kwargs: HTMLAttributeValue) -> Element: ...

class _VEl(type):
  def __getitem__(cls, name: str) -> CreateHTMLVoidElement:
    def _inner(key: str | None = None, **kwargs: HTMLAttributeValue) -> Element:
      el = HTMLVoidElement(name, attributes={ k.lstrip("_"): v for k,v in kwargs.items() })
      if key is not None: el = KeyedElement(key, el)
      return el
    return _inner
  def __getattribute__(cls, name: str): return cls[name]

class VEl(metaclass=_VEl): ...

class ElementFactory(Protocol):
  def __call__(self) -> Element: ...

def meta_element(id: str, inner: Element): return HTMLElement("rxxxt-meta", {"id":id}, [inner])
