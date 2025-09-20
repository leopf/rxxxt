import html, itertools, logging
from abc import ABC, abstractmethod
from typing import Callable, Concatenate, Generic, Protocol, cast
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

def _element_content_to_ordered_nodes(context: Context, content: ElementContent) -> tuple[Node, ...]:
  return tuple((TextElement(item) if isinstance(item, str) else item).tonode(context.sub(idx)) for idx, item in enumerate(content))

def _merge_attribute_values(k: str, values: tuple[HTMLAttributeValue, ...]):
  if len(values) == 1: return values[0]
  if k == "style" and all(isinstance(v, str) for v in values): return ";".join(cast(tuple[str,...], values))
  if k == "class" and all(isinstance(v, str) for v in values): return " ".join(cast(tuple[str,...], values))
  raise ValueError(f"failed to merge attribute '{k}' with values {repr(values)}.")

def _merge_attribute_items(attrs: Iterable[tuple[str, HTMLAttributeValue]]):
  normalized = sorted(((k.lstrip("_"), v) for k, v in attrs), key=lambda item: item[0])
  return ((k, _merge_attribute_values(k, tuple(item[1] for item in g))) for k,g in itertools.groupby(normalized, key=lambda item: item[0]))

def _html_attributes_to_kv(attributes: HTMLAttributes):
  fattributes: dict[str, str | None] = {}
  items = _merge_attribute_items((k, v) for ok, ov in attributes.items()
    for k, v in (ov.get_key_values(ok) if isinstance(ov, CustomAttribute) else ((ok, ov),)))
  for k, v in items:
    if v is False: continue
    elif v is True: v = None
    elif isinstance(v, (int, float)): v = str(v)
    if v is not None and not isinstance(v, str):
      raise ValueError("Invalid attribute value", v)
    fattributes[k] = v
  return fattributes

# to make elements that dont have state and are transformed to node 1:1
class _FnElement(Element, Generic[FNP]):
  def __init__(self, fn: Callable[Concatenate[Context, FNP], Node], *args: FNP.args, **kwargs: FNP.kwargs) -> None:
    self._fn = fn
    self._fn_args = args
    self._fn_kwargs = kwargs

  def tonode(self, context: Context) -> 'Node':
    return self._fn(context, *self._fn_args, **self._fn_kwargs)

def fn_element(fn: Callable[Concatenate[Context, FNP], Node]) -> Callable[FNP, 'Element']:
  def _inner(*args: FNP.args, **kwargs: FNP.kwargs) -> Element:
    return _FnElement(fn, *args, **kwargs)
  return _inner

def lazy_element(fn: Callable[Concatenate[Context, FNP], Element]) -> Callable[FNP, 'Element']:
  def _inner(context: Context, *args: FNP.args, **kwargs: FNP.kwargs) -> Node:
    return fn(context, *args, **kwargs).tonode(context)
  return fn_element(_inner)

@fn_element
def HTMLFragment(context: Context, content: ElementContent):
  return FragmentNode(context, _element_content_to_ordered_nodes(context, content))

@fn_element
def HTMLVoidElement(context: Context, tag: str, attributes: HTMLAttributes):
  return VoidElementNode(context, tag, _html_attributes_to_kv(attributes))

@fn_element
def HTMLElement(context: Context, tag: str, attributes: HTMLAttributes, content: ElementContent):
  return ElementNode(context, tag, _html_attributes_to_kv(attributes), _element_content_to_ordered_nodes(context, content))

@fn_element
def KeyedElement(context: Context, key: str, element: Element):
  try: context = context.replace_index(key)
  except ValueError as e: logging.debug(f"Failed to replace index with key {key}", e)
  return element.tonode(context)

@fn_element
def TaggedElement(context: Context, tag: str, element: Element):
  return element.tonode(context = context.sub(tag))

@fn_element
def WithRegistered(context: Context, register: dict[str, Any], child: Element):
  return child.tonode(context.update_registry(register))

@fn_element
def TextElement(context: Context, text: str):
  return TextNode(context, html.escape(text))

@fn_element
def UnescapedHTMLElement(context: Context, text: str):
  return TextNode(context, text)

@fn_element
def ScriptContent(context: Context, script: str):
  return TextNode(context, script.replace("</", "<\\/"))

def _create_el(name: str, attributes: HTMLAttributes, content: ElementContent | None) -> Element:
  attributes = dict(_merge_attribute_items(attributes.items()))
  key = attributes.pop("key", None)
  el = HTMLVoidElement(name, attributes=attributes) if content is None else HTMLElement(name, attributes=attributes, content=list(content))
  if isinstance(key, str): el = KeyedElement(key, el)
  return el

class CreateHTMLElement(Protocol):
  def __call__(self, content: ElementContent = (), **kwargs: HTMLAttributeValue) -> Element: ...

class _El(type):
  def __getitem__(cls, name: str) -> CreateHTMLElement:
    def _inner(content: ElementContent = (), **kwargs: HTMLAttributeValue):
      return _create_el(name, kwargs, content)
    return _inner
  def __getattribute__(cls, name: str):
    return cls[name]

class El(metaclass=_El): ...

class CreateHTMLVoidElement(Protocol):
  def __call__(self, **kwargs: HTMLAttributeValue) -> Element: ...

class _VEl(type):
  def __getitem__(cls, name: str) -> CreateHTMLVoidElement:
    def _inner(**kwargs: HTMLAttributeValue) -> Element:
      return _create_el(name, kwargs, None)
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

def merge_attributes(a: HTMLAttributes, b: HTMLAttributes):
  return dict(_merge_attribute_items(itertools.chain(a.items(), b.items())))

def add_attributes(base: HTMLAttributes, **kwargs: HTMLAttributeValue):
  return merge_attributes(kwargs, base)
