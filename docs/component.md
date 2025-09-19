# [`Component`](./api.md#rxxxt.component.Component)

Components are stateful html elements that overwrite [`Component`](./api.md#rxxxt.component.Component).

They can modify and read state, see the [state documentation](./state.md#with-components).

To render a component the [`render`](./api.md#rxxxt.component.Component.render) function must be overwritten.

A simple counter component:
```python
class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])
```

[`HandleNavigate`](./api.md#rxxxt.component.HandleNavigate) can be used as an attribute helper when you only need navigation.

## Events
Components can receive user input events using the [`event_handler`](./api.md#rxxxt.component.event_handler) decorator.

Like:
```python
@event_handler()
def on_click(self):
  self.count += 1
```

Event handlers can receive [`ContextInputEventHandlerOptions`](./api.md#rxxxt.events.ContextInputEventHandlerOptions).

Parameters on event handlers can be pre-filled with [`EventHandler.bind`](./api.md#rxxxt.component.EventHandler.bind):
```python
class Counter(Component):
  count = local_state(int)

  @event_handler()
  def increase(self, amount: int):
    self.count += amount

  def render(self) -> Element:
    return El.div(content=[
      El.button(onclick=self.increase.bind(amount=5), content=["Add 5"]),
      El.button(onclick=self.increase.bind(amount=1), content=["Add 1"]),
    ])
```
`bind` returns a new handler instance using the provided default parameters.

The event handlers can then be used as html attributes for the desired events. For example the, `onclick` event:
```python
El.div(onclick=self.on_click, content=[f"Count: {self.count}"])
```

To receive event data from an html event, you can use the `Annotated` type to specify which fields you would like to map to which function parameter.

In the following example the event data `target.value` is selected from the `change` event of the rendered input element and passed as the `value` parameter.

```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element

class InputExample(Component):
  @event_handler()
  def on_change(self, value: Annotated[str, "target.value"]):
    print("The user entered ", value)

  def render(self) -> Element:
    return VEl.input(onchange=self.on_change, type="text")
```

### Custom output events
[`Context.emit`](./api.md#rxxxt.execution.Context.emit) lets a component notify the browser about arbitrary events.
The event name is a string and the payload must be JSON-compatible primitives (`int`, `float`, `str`, `bool` or `None`).

On the browser side, handlers can be registered through `window.rxxxt.on`.

```python
from rxxxt import App, Component, Element, El, PageBuilder, UnescapedHTMLElement, event_handler

class Export(Component):
  @event_handler()
  def download(self):
    self.context.emit("download", {"url": "https://example.com/archive.zip", "name": "archive.zip"})

  def render(self) -> Element:
    return El.button(onclick=self.download, content=["Download archive"])

page = PageBuilder()
page.add_body_end(El.script(content=[
  UnescapedHTMLElement("""
    rxxxt.on("download", data => {
      const link = document.createElement("a");
      link.download = data.name;
      link.href = data.url;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
    });
  """)
]))

app = App(Export, page_factory=page)
```

Handlers can be removed with `window.rxxxt.off(name, handler)`.

## Background tasks
Background tasks only run when a session is persistent (using websockets).

They can be created in two ways:

- `add_job` - creates a task from a coroutine that must be run until finished
- `add_worker` - creates a task from a coroutine that runs in the background until the component is destroyed. Can be cancelled at any time.


## Lifecycle
A component is alive as long as its parent is not updated.

Events:

- `on_init` - when the component is initialized
- `on_before_destroy` - before all background tasks are destroyed
- `on_after_destroy` - after all background tasks are destroyed

## Context
A lot of functionality that is available to components lives inside the component [`Context`](./api.md#rxxxt.execution.Context).

#### use websocket, request updates
- `use_websocket`
- `request_update`

#### access headers, path, query_string, navigate, set/get cookies
properties:

- `cookies`
- `location`
- `path`
- `query_string`

methods:

- `get_header`
- `set_cookie` (`mirror_state` controls whether the cookie header is updated in state)
- `delete_cookie` (also honours `mirror_state`)
- `navigate`
- `match_path`

#### manage subscriptions
- `subscribe`
- `unsubscribe`
- `unsubscribe_all`

#### add/remove events to the window or elements selected by a query selector
- `add_query_selector_event`
- `add_window_event`
- `remove_query_selector_event`
- `remove_window_event`
