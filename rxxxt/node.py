
from abc import ABC
import base64, html, inspect
from io import StringIO
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints, override
from rxxxt.execution import Context, InputEvent, InputEventDescriptor, InputEventDescriptorOptions
from rxxxt.helpers import to_awaitable

class Node(ABC):
  def __init__(self, context: Context, children: tuple['Node', ...]) -> None:
    self.context = context
    self.children = children

  async def expand(self):
    for c in self.children:
      await c.expand()

  async def update(self):
    for c in self.children:
      await c.update()

  async def handle_event(self, event: InputEvent):
    for c in self.children:
      await c.handle_event(event)

  async def destroy(self):
    for c in self.children:
      await c.destroy()

  def write(self, io: StringIO):
    for c in self.children:
      c.write(io)

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

  def write(self, io: StringIO):
    _ = io.write(self.text)

def _write_opening_tag(io: StringIO, tag: str, attributes: tuple['Node', ...]):
  _ = io.write(f"<{html.escape(tag)}")
  for a in attributes:
    io.write(" ")
    a.write(io)
  _ = io.write(">")

class VoidElementNode(Node):
  def __init__(self, context: Context, tag: str, attributes: tuple['Node', ...]) -> None:
    super().__init__(context, attributes)
    self.attributes = attributes
    self.tag = tag

  def write(self, io: StringIO):
    _write_opening_tag(io, self.tag, self.attributes)

class ElementNode(Node):
  def __init__(self, context: Context, tag: str, attributes: tuple['Node', ...], content: tuple['Node', ...]) -> None:
    super().__init__(context, attributes + content)
    self.tag = tag
    self.attributes = attributes
    self.content = content

  def write(self, io: StringIO):
    _write_opening_tag(io, self.tag, self.attributes)
    for c in self.content:
      c.write(io)
    _ = io.write(f"</{html.escape(self.tag)}>")

class EventHandlerNode(Node):
  def __init__(self, context: Context, event_name: str, handler: Callable, bound: tuple[Any,...], options: InputEventDescriptorOptions) -> None:
    super().__init__(context, ())
    self.event_name = event_name
    self.handler = handler
    self.options = options
    self.bound = bound

  @property
  def _param_map(self):
    param_map: dict[str, str] = {}
    sig = inspect.signature(self.handler)
    hints = get_type_hints(self.handler, include_extras=True)
    for i, (name, param) in enumerate(sig.parameters.items()):
      if i == 0: continue  # skip self
      ann = hints.get(name, param.annotation)
      if get_origin(ann) is Annotated:
        args = get_args(ann)
        metadata = args[1:]
        if len(metadata) < 1:
          raise ValueError(f"Parameter '{name}' is missing the second annotation.")
        if not isinstance(metadata[0], str):
          raise TypeError(f"Parameter '{name}' second annotation must be a str, got {type(metadata[0]).__name__}.")
        param_map[name] = metadata[0]
    return param_map

  async def handle_event(self, event: InputEvent):
    if event.context_id == self.context.sid:
      await to_awaitable(self.handler, *self.bound, **event.data)

  def write(self, io: StringIO):
    v = base64.b64encode(InputEventDescriptor(context_id=self.context.sid, param_map=self._param_map, \
      options=self.options).model_dump_json().encode("utf-8")).decode("utf-8")

    io.write(f"rxxxt-on-{html.escape(self.event_name)}=\"{html.escape(v)}\"")
