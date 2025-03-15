from abc import ABC, abstractmethod
import asyncio
from functools import cached_property
import hashlib
import html
from io import StringIO
import logging
from typing import Awaitable, Coroutine, Protocol
from rxxxt.helpers import to_awaitable

ContextStackKey = str | int
ContextStack = tuple[ContextStackKey, ...]

class Execution:
  def __init__(self, initial_state: dict[str, str]) -> None:
    self._state: dict[str, str] = initial_state
    self._state_subscribers: dict[str, set[ContextStack]] = {}
    self._pending_updates: set[ContextStack] = set()

  def get_state(self, context_id: ContextStack, key: str) -> str | None:
    self._state_subscribers.setdefault(key, set()).add(context_id)
    return self._state.get(key)

  def set_state(self, key: str, value: str | None):
    if value != self._state.get(key, None):
      for cid in self._state_subscribers.get(key, []): self._pending_updates.add(cid)
      if value is None: self._state.pop(key, None)
      else: self._state[key] = value

  def request_update(self, cid: ContextStack): self._pending_updates.add(cid)

class Context:
  def __init__(self, execution: Execution, stack: ContextStack) -> None:
    self._stack: ContextStack = stack
    self._execution = execution

  @cached_property
  def id(self):
    hasher = hashlib.sha256()
    for k in self._stack:
      if isinstance(k, str): k = k.replace(";", ";;")
      else: k = str(k)
      hasher.update((k + ";").encode("utf-8"))
    return hasher.hexdigest()

  def sub(self, key: ContextStackKey): return Context(self._execution, self._stack + (key,))
  def replace_index(self, key: str):
    if isinstance(self._stack[-1], int): return Context(self._execution, self._stack[:-1] + (key,))
    raise ValueError("No index to replace!")

class Node(ABC):
  def __init__(self, context: Context, children: list['Node']) -> None:
    self.context = context
    self.children = children

  async def expand(self):
    for c in self.children: await c.expand()

  async def update(self):
    for c in self.children: await c.update()

  async def destroy(self):
    for c in self.children: await c.destroy()

  def write(self, io: StringIO):
    for c in self.children: c.write(io)

class FragementNode(Node): ...
class TextNode(Node):
  def __init__(self, context: Context, text: str) -> None:
    super().__init__(context, [])
    self.text = text

  def write(self, io: StringIO): io.write(self.text)

class VoidElementNode(Node):
  def __init__(self, context: Context, tag: str, attributes: dict[str, str | None], children: list['Node'] = []) -> None:
    super().__init__(context, children)
    self.attributes = attributes
    self.tag = tag

  def write(self, io: StringIO):
    io.write(f"<{html.escape(self.tag)}")
    for k, v in self.attributes:
      io.write(f" {html.escape(k)}")
      if v is not None: io.write(f"={html.escape(v)}")
    io.write(">")

class ElementNode(VoidElementNode):
  def __init__(self, context: Context, tag: str, attributes: dict[str, str | None], children: list['Node']) -> None:
    super().__init__(context, tag, attributes, children)

  def write(self, io: StringIO):
    super().write(io)
    for c in self.children: c.write(io)
    io.write(f"</{html.escape(self.tag)}>")

class RenderedElementNode(Node):
  def __init__(self, context: Context, element: 'RenderedElement') -> None:
    super().__init__(context, [])
    self.element = element

  async def expand(self):
    if len(self.children) > 0:
      raise ValueError("Can not expand already expanded element!")

    inner = await to_awaitable(self.element.render)
    self.children.append(inner.tonode(self.context.sub("inner")))
    await self.children[0].expand()


# TODO: error handling!!
class ComonentNode(Node):
  def __init__(self, context: Context, element: 'Component') -> None:
    super().__init__(context, [])
    self.element = element
    self.background_tasks: list[asyncio.Task] = []

  async def expand(self):
    if len(self.children) > 0:
      raise ValueError("Can not expand already expanded element!")

    self.element.lc_configure(self.context)
    await to_awaitable(self.element.lc_init)

    for a in self.element.background_tasks:
      self.background_tasks.append(asyncio.create_task(a))

    await self._render_inner()

  async def update(self):
    for c in self.children: await c.destroy()
    self.children.clear()
    await self._render_inner()

  async def destroy(self):
    for c in self.children: await c.destroy()
    self.children.clear()

    await to_awaitable(self.element.lc_before_destroyed)

    for t in self.background_tasks: t.cancel()
    try: await asyncio.wait(self.background_tasks)
    except asyncio.CancelledError: pass

    await to_awaitable(self.element.lc_after_destroy)

  async def _render_inner(self):
    inner = await to_awaitable(self.element.render)
    self.children.append(inner.tonode(self.context.sub("inner")))
    await self.children[0].expand()

# --- elements

class CustomAttribute(ABC):
  @abstractmethod
  def get_key_value(self, original_key: str) -> tuple[str, str | None]: ...

class Element(ABC):
  @abstractmethod
  def tonode(self, context: Context) -> 'Node': ...

ElementContent = list[Element | str]
HTMLAttributeValue = str | bool | int | float | CustomAttribute | None

def element_content_to_nodes(context: Context, content: ElementContent):
  nodes: list[Node] = []
  for idx, c in enumerate(content):
    scontext = context.sub(idx)
    if isinstance(c, Element): nodes.append(c.tonode(scontext))
    elif isinstance(c, str): nodes.append(TextNode(scontext, html.escape(c)))
    else: raise ValueError("Invalid child!")
  return nodes;

class HTMLFragement(Element):
  def __init__(self, content: ElementContent) -> None:
    super().__init__()
    self._content = content

  def tonode(self, context: Context) -> Node:
    return FragementNode(context, element_content_to_nodes(context, self._content))

class HTMLVoidElement(Element):
  def __init__(self, tag: str, attributes: dict[str, HTMLAttributeValue]) -> None:
    super().__init__()
    self._tag = tag
    self._attributes: dict[str, str | None] = {}
    for k, v in attributes.items():
      if isinstance(v, CustomAttribute): k, v = v.get_key_value(k)
      elif isinstance(v, (int, float)): v = str(v)
      elif isinstance(v, bool):
        if not v: continue
        v = None
      self._attributes[k] = v

  def tonode(self, context: Context) -> 'Node':
    return VoidElementNode(context, self._tag, self._attributes)

class HTMLElement(HTMLVoidElement):
  def __init__(self, tag: str, attributes: dict[str, HTMLAttributeValue], content: ElementContent) -> None:
    super().__init__(tag, attributes)
    self._content = content

  def tonode(self, context: Context) -> 'Node':
    return ElementNode(context, self._tag, self._attributes, element_content_to_nodes(context, self._content))

class KeyedElement(Element):
  def __init__(self, key: str, element: Element) -> None:
    super().__init__()
    self._key = key
    self._element = element

  def tonode(self, context: Context) -> 'Node':
    try: context = context.replace_index(self._key)
    except ValueError as e: logging.warning(f"Failed to replace index with key {self._key}", e)
    return self._element.tonode(context)

class UnescapedHTMLElement(Element):
  def __init__(self, text: str) -> None:
    super().__init__()
    self._text = text

  def tonode(self, context: Context) -> 'Node': return TextNode(context, self._text)

class RenderedElement(Element):
  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: ...

  def tonode(self, context: Context) -> 'Node': return RenderedElementNode(context, self)

class Component(Element):
  def __init__(self) -> None:
    super().__init__()
    self.context: Context | None = None
    self.background_tasks: list[Coroutine] = []

  @abstractmethod
  def render(self) -> Element | Awaitable[Element]: ...

  def add_background_task(self, a: Coroutine): self.background_tasks.append(a)

  def lc_configure(self, context: Context): self.context = context
  def lc_init(self) -> None | Awaitable[None]: return self.on_init()
  def lc_before_destroyed(self) -> None | Awaitable[None]: return self.on_before_destroy()
  def lc_after_destroy(self) -> None | Awaitable[None]: return self.on_after_destroy()

  def on_init(self) -> None | Awaitable[None]: ...
  def on_before_destroy(self) -> None | Awaitable[None]: ...
  def on_after_destroy(self) -> None | Awaitable[None]: ...

class CreateHTMLElement(Protocol):
  def __call__(self, content: list[Element | str] = [], key: str | None = None, **kwargs: str | CustomAttribute | None) -> Element: ...

class _El(type):
  def __getitem__(cls, name: str) -> CreateHTMLElement:
    def _inner(content: ElementContent = [], key: str | None = None, **kwargs: str | CustomAttribute | None):
      el = HTMLElement(name, attributes={ k.lstrip("_"): v for k,v in kwargs.items() }, content=content)
      if key is not None: el = KeyedElement(key, el)
      return el
    return _inner
  def __getattribute__(cls, name: str): return cls[name]

class El(metaclass=_El): ...

class CreateHTMLVoidElement(Protocol):
  def __call__(self, **kwargs: str | CustomAttribute | None) -> HTMLVoidElement: ...

class _VEl(type):
  def __getitem__(cls, name: str) -> CreateHTMLVoidElement:
    def _inner(**kwargs: str | CustomAttribute | None) -> HTMLVoidElement:
      return HTMLVoidElement(name, attributes={ k.lstrip("_"): v for k,v in kwargs.items() })
    return _inner
  def __getattribute__(cls, name: str): return cls[name]

class VEl(metaclass=_VEl): ...

class ElementFactory(Protocol):
  def __call__(self) -> Element: ...

class ElementFactoryElement(RenderedElement):
  def __init__(self, factory: ElementFactory) -> None:
    super().__init__()
    self._factory = factory

  def render(self) -> Element: return self._factory()
