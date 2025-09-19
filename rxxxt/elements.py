from abc import ABC, abstractmethod
import html
import logging
from typing import Callable, Concatenate, Generic, Protocol
from collections.abc import Iterable
from rxxxt.execution import Context
from rxxxt.helpers import FNP
from rxxxt.node import ElementNode, FragmentNode, Node, TextNode, VoidElementNode
from typing import Any

class Element(ABC):
  @abstractmethod
  def tonode(self, context: Context) -> Node: ...

class CustomAttribute(ABC):
  @abstractmethod
  def get_key_values(self, original_key: str) -> tuple[tuple[str, str | None],...]: ...

ElementContent = Iterable[Element | str]
HTMLAttributeValue = str | bool | int | float | CustomAttribute | None
HTMLAttributes = dict[str, str | bool | int | float | CustomAttribute | None]

def _elements_to_ordered_nodes(context: Context, elements: tuple[Element, ...]):
  return tuple(el.tonode(context.sub(idx)) for idx, el in enumerate(elements))

def _element_content_to_elements(content: ElementContent) -> tuple[Element, ...]:
  return tuple(TextElement(item) if isinstance(item, str) else item for item in content)

def _normalize_attrs(attrs: HTMLAttributes):
  return { k.lstrip("_"): v for k,v in attrs.items() }

def _apply_attribute_kv(attributes: dict[str, str | None], k: str, v: Any):
  if isinstance(v, bool):
    if not v: return
    v = None
  elif isinstance(v, (int, float)): v = str(v)
  if v is not None and not isinstance(v, str):
    raise ValueError("Invalid attribute value", v)
  attributes[k] = v

class HTMLFragment(Element):
  def __init__(self, content: ElementContent) -> None:
    super().__init__()
    self._content = _element_content_to_elements(content)

  def tonode(self, context: Context) -> Node:
    return FragmentNode(context, _elements_to_ordered_nodes(context, self._content))

class HTMLVoidElement(Element):
  def __init__(self, tag: str, attributes: HTMLAttributes) -> None:
    super().__init__()
    self._tag = tag
    self._attributes: dict[str, str | None] = {}
    for k, v in attributes.items():
      if isinstance(v, CustomAttribute):
        for ik, iv in v.get_key_values(k):
          _apply_attribute_kv(self._attributes, ik, iv)
      else:
        _apply_attribute_kv(self._attributes, k, v)

  def tonode(self, context: Context) -> 'Node':
    return VoidElementNode(context, self._tag, self._attributes)

class HTMLElement(HTMLVoidElement):
  def __init__(self, tag: str, attributes: HTMLAttributes, content: ElementContent) -> None:
    super().__init__(tag, attributes)
    self._content = _element_content_to_elements(content)

  def tonode(self, context: Context) -> 'Node':
    return ElementNode(context, self._tag, self._attributes, _elements_to_ordered_nodes(context, self._content))

class KeyedElement(Element):
  def __init__(self, key: str, element: Element) -> None:
    super().__init__()
    self._key = key
    self._element = element

  def tonode(self, context: Context) -> 'Node':
    try: context = context.replace_index(self._key)
    except ValueError as e: logging.debug(f"Failed to replace index with key {self._key}", e)
    return self._element.tonode(context)

class TaggedElement(Element):
  def __init__(self, tag: str, element: Element) -> None:
    super().__init__()
    self._tag = tag
    self._element = element

  def tonode(self, context: Context) -> 'Node':
    return self._element.tonode(context = context.sub(self._tag))

class WithRegistered(Element):
  def __init__(self, register: dict[str, Any], child: Element) -> None:
    super().__init__()
    self._register = register
    self._child = child

  def tonode(self, context: Context) -> 'Node':
    return self._child.tonode(context.update_registry(self._register))

class _LazyElement(Element, Generic[FNP]):
  def __init__(self, fn: Callable[Concatenate[Context, FNP], Node], *args: FNP.args, **kwargs: FNP.kwargs) -> None:
    self._fn = fn
    self._fn_args = args
    self._fn_kwargs = kwargs

  def tonode(self, context: Context) -> 'Node':
    return self._fn(context, *self._fn_args, **self._fn_kwargs)

def lazy_node(fn: Callable[Concatenate[Context, FNP], Node]) -> Callable[FNP, 'Element']:
  def _inner(*args: FNP.args, **kwargs: FNP.kwargs) -> Element:
    return _LazyElement(fn, *args, **kwargs)
  return _inner

def lazy_element(fn: Callable[Concatenate[Context, FNP], Element]) -> Callable[FNP, 'Element']:
  def _inner(context: Context, *args: FNP.args, **kwargs: FNP.kwargs) -> Node:
    return fn(context, *args, **kwargs).tonode(context)
  return lazy_node(_inner)

@lazy_node
def TextElement(context: Context, text: str):
  return TextNode(context, html.escape(text))

@lazy_node
def UnescapedHTMLElement(context: Context, text: str):
  return TextNode(context, text)

@lazy_node
def ScriptContent(context: Context, script: str):
  return TextNode(context, script.replace("</", "<\\/"))

class CreateHTMLElement(Protocol):
  def __call__(self, content: ElementContent = (), key: str | None = None, **kwargs: HTMLAttributeValue) -> Element: ...

class _El(type):
  def __getitem__(cls, name: str) -> CreateHTMLElement:
    def _inner(content: ElementContent = (), key: str | None = None, **kwargs: HTMLAttributeValue):
      el = HTMLElement(name, attributes=_normalize_attrs(kwargs), content=list(content))
      if key is not None: el = KeyedElement(key, el)
      return el
    return _inner
  def __getattribute__(cls, name: str):
    return cls[name]

class El(metaclass=_El): ...

class CreateHTMLVoidElement(Protocol):
  def __call__(self, key: str | None = None, **kwargs: HTMLAttributeValue) -> Element: ...

class _VEl(type):
  def __getitem__(cls, name: str) -> CreateHTMLVoidElement:
    def _inner(key: str | None = None, **kwargs: HTMLAttributeValue) -> Element:
      el = HTMLVoidElement(name, attributes=_normalize_attrs(kwargs))
      if key is not None: el = KeyedElement(key, el)
      return el
    return _inner
  def __getattribute__(cls, name: str):
    return cls[name]

class VEl(metaclass=_VEl): ...

class ElementFactory(Protocol):
  def __call__(self) -> Element: ...

def meta_element(id: str, inner: Element):
  return HTMLElement("rxxxt-meta", {"id":id}, [inner])

def class_map(map: dict[str, bool]):
  return " ".join([ k for k, v in map.items() if v ])

def css_extend(attrs: HTMLAttributes, class_attr: str = "", style_attr: str = ""):
  attrs = _normalize_attrs(attrs)
  if class_attr:
    if "class" in attrs: attrs["class"] = (str(attrs["class"]) + " " + class_attr).strip()
    else: attrs["class"] = class_attr
  if style_attr:
    if "style" in attrs: attrs["style"] = (str(attrs["style"]) + ";" + style_attr).strip()
    else: attrs["style"] = style_attr
  return attrs
