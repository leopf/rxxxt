
from io import StringIO
from rxxxt.events import InputEvent
from rxxxt.execution import ContextStack
from rxxxt.node import Node

def render_node(node: Node) -> str:
  io = StringIO()
  node.write(io)
  return io.getvalue()

class Renderer:
  def __init__(self, root: Node) -> None:
    self._root = root
    self._pending_renders: set[ContextStack] = set()

  async def expand(self): await self._root.expand()

  async def update(self, ids: set[ContextStack]):
    for node in self._find_roots(ids):
      self._pending_renders.add(node.context.id)
      await node.update()

  async def handle_events(self, events: tuple[InputEvent, ...]):
    await self._root.handle_events(events)

  async def destroy(self): await self._root.destroy()

  def render_full(self) -> str:
    self._pending_renders.clear()
    return render_node(self._root)

  def render_partial(self):
    res = tuple(render_node(node) for node in self._find_roots(self._pending_renders))
    self._pending_renders.clear()
    return res

  def _find_roots(self, ids: set[ContextStack]):
    if self._root.context.id in ids:
      yield self._root
      return
    els: list[Node] = [self._root]

    while len(els) > 0:
      nels: list[Node] = []
      for nel in (nel for el in els for nel in el.children):
        if nel.context.id in ids: yield nel
        else: nels.append(nel)
      els = nels
