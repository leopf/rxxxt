
from abc import ABC
import html
from io import StringIO
from typing import Callable
from rxxxt.events import InputEvent
from rxxxt.execution import Context

class Node(ABC):
  def __init__(self, context: Context, children: tuple['Node', ...]) -> None:
    self.context = context
    self.children = children

  async def expand(self):
    for c in self.children: await c.expand()

  async def update(self):
    for c in self.children: await c.update()

  async def handle_event(self, event: InputEvent):
    for c in self.children: await c.handle_event(event)

  async def destroy(self):
    for c in self.children: await c.destroy()

  def write(self, io: StringIO):
    for c in self.children: c.write(io)

class LazyNode(Node):
  def __init__(self, context: Context, producer: Callable[[Context], Node]) -> None:
    super().__init__(context, ())
    self._producer: Callable[[Context], Node] = producer

  async def expand(self):
    if self.children == ():
      self.children = (self._producer(self.context),)
    return await super().expand()

class FragmentNode(Node): ...
class TextNode(Node):
  def __init__(self, context: Context, text: str) -> None:
    super().__init__(context, ())
    self.text = text

  def write(self, io: StringIO): _ = io.write(self.text)

class VoidElementNode(Node):
  def __init__(self, context: Context, tag: str, attributes: dict[str, str | None], children: tuple['Node', ...] = ()) -> None:
    super().__init__(context, children)
    self.attributes = attributes
    self.tag = tag

  def write(self, io: StringIO):
    _ = io.write(f"<{html.escape(self.tag)}")
    for k, v in self.attributes.items():
      _ = io.write(f" {html.escape(k)}")
      if v is not None: _ = io.write(f"=\"{html.escape(v)}\"")
    _ = io.write(">")

class ElementNode(VoidElementNode):
  def __init__(self, context: Context, tag: str, attributes: dict[str, str | None], children: tuple['Node', ...]) -> None:
    super().__init__(context, tag, attributes, children)

  def write(self, io: StringIO):
    super().write(io)
    for c in self.children: c.write(io)
    _ = io.write(f"</{html.escape(self.tag)}>")
