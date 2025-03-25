
from abc import ABC
import html
from io import StringIO
from rxxxt.events import InputEvent
from rxxxt.execution import Context

class Node(ABC):
  def __init__(self, context: Context, children: list['Node']) -> None:
    self.context = context
    self.children = children

  async def expand(self):
    for c in self.children: await c.expand()

  async def update(self):
    for c in self.children: await c.update()

  async def handle_events(self, events: list[InputEvent]):
    for c in self.children: await c.handle_events(events)

  async def destroy(self):
    for c in self.children: await c.destroy()

  def write(self, io: StringIO):
    for c in self.children: c.write(io)

class FragmentNode(Node): ...
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
    for k, v in self.attributes.items():
      io.write(f" {html.escape(k)}")
      if v is not None: io.write(f"=\"{html.escape(v)}\"")
    io.write(">")

class ElementNode(VoidElementNode):
  def __init__(self, context: Context, tag: str, attributes: dict[str, str | None], children: list['Node']) -> None:
    super().__init__(context, tag, attributes, children)

  def write(self, io: StringIO):
    super().write(io)
    for c in self.children: c.write(io)
    io.write(f"</{html.escape(self.tag)}>")
