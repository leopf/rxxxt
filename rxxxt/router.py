import typing
from rxxxt.elements import El, Element, ElementFactory, TaggedElement
from rxxxt.component import Component, context_state
from rxxxt.helpers import match_path

def router_params(): return context_state(dict[str, str], "*rp*")

class Router(ElementFactory):
  class RoutedComponent(Component):
    params = router_params()

    def __init__(self, routes: tuple[tuple[str, ElementFactory], ...]):
      super().__init__()
      self._routes = routes
      self._selected_match: tuple[int, ElementFactory, dict[str, str]] | None = None

    async def on_before_update(self) -> None:
      self._selected_match = self._get_current_match()
      self.params = typing.cast(dict[str, str], dict()) if self._selected_match is None else self._selected_match[2]

    def render(self) -> Element:
      if self._selected_match is None:
        return El.h1(content=["Not found!"])
      else:
        return TaggedElement(str(self._selected_match[0]), self._selected_match[1]())

    def _get_current_match(self):
      path = self.context.path
      for idx, (pattern, element_factory) in enumerate(self._routes):
        if (m:=match_path(pattern, path)) is not None:
          return (idx, element_factory, m)
      return None

  def __init__(self) -> None:
    self._routes: list[tuple[str, ElementFactory]] = []

  def add_router(self, router: 'Router'): self._routes.extend(router._routes)
  def add_route(self, pattern: str, element_factory: ElementFactory): self._routes.append((pattern, element_factory))
  def route(self, pattern: str):
    def _inner(fn: ElementFactory):
      self.add_route(pattern, fn)
      return fn
    return _inner

  def __call__(self) -> Element: return Router.RoutedComponent(tuple(self._routes))
