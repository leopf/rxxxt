import uvicorn
from typing import Annotated
from pydantic import BaseModel
from rxxxt import Component, event_handler, El, VEl, Element, App, local_state, local_state_box, PageBuilder


class TodoItem(BaseModel):
  text: str
  done: bool = False


class TodoApp(Component):
  items = local_state_box(list[TodoItem])
  new_item = local_state(str)

  @event_handler(prevent_default=True)
  def add_item(self):
    if self.new_item.strip():
      with self.items as items:
        items.append(TodoItem(text=self.new_item))
      self.new_item = ""

  def toggle_item(self, index: int):
    with self.items as items:
      items[index].done = not items[index].done

  def delete_item(self, index: int):
    with self.items as items:
      items.pop(index)

  @event_handler(throttle=500, debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.new_item = value

  def render(self) -> Element:
    return El.main(
      _class="container",
      content=[
        El.h1(content=["Todo List"], style="margin-top: 2rem;"),
        self._render_input_form(),
        self._render_list(),
        El.small(content=[f"{len([i for i in self.items.value if i.done])} of {len(self.items.value)} completed"]),
      ],
    )

  def _render_input_form(self) -> Element:
    return El.form(
      onsubmit=self.add_item,
      content=[
        El.input_group(
          style="display: flex; gap: 0.5rem; margin-bottom: 1rem;",
          content=[
            VEl.input(
              oninput=self.on_input,
              value=self.new_item,
              placeholder="What needs to be done?",
              aria_label="New todo",
              style="flex: 1;",
            ),
            El.button(content=["Add"], style="height: auto; padding: 0.6rem 1rem;"),
          ],
        ),
      ],
    )

  def _render_list(self) -> Element:
    if self.items.value:
      return El.ul(
        content=[self._render_item(item, i) for i, item in enumerate(self.items.value)], role="list", style="list-style: none; padding: 0;"
      )
    return El.article(content=[El.em(content=["No todos yet! Add one above."])])

  def _render_item(self, item: TodoItem, index: int) -> Element:
    return El.li(
      content=[
        El.label(
          content=[
            VEl.input(
              _type="checkbox",
              checked=item.done,
              onchange=lambda: self.toggle_item(index),
            ),
            El.span(content=[item.text], style="text-decoration: line-through; opacity: 0.5" if item.done else ""),
          ]
        ),
        El.button(
          _class="secondary outline",
          onclick=lambda: self.delete_item(index),
          aria_label="Delete",
          style="padding: 0.1rem 0.4rem; font-size: 0.8rem;",
          content=["×"],
        ),
      ],
      style="display: flex; justify-content: space-between; align-items: center; list-style: none;",
    )


page_builder = PageBuilder()
page_builder.add_stylesheet("https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css")

app = App(TodoApp, page_factory=page_builder)
uvicorn.run(app)
