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

## Events
Components can receive user input events using the [`event_handler`](./api.md#rxxxt.component.event_handler) decorator.

Like:
```python
@event_handler()
def on_click(self):
  self.count += 1
```

Event handlers can receive [`EventHandlerOptions`](./api.md#rxxxt.component.EventHandlerOptions).

The event handlers can then be used as html attributes for the desired events. For example the, `onclick` event:
```python
El.div(onclick=self.on_click, content=[f"Count: {self.count}"])
```

To receive event data from an html event, you can use the `Annotate` type to specify which fields you would like to map to which function parameter.

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


## Background tasks
Background tasks only run when a session is persistent (using websockets).

They can be created in two ways:

- `add_job` - creates a task from a coroutine that must be run until finished
- `add_worker` - creates a task from a couroutine that runs in the background until the component is destroyed. Can be cancelled at any time.


## Lifecycle
A component is alive as long as its parent is not updated.

Events:

- `on_init` - when the component is initialized
- `on_before_destroy` - before all background tasks are destroyed
- `on_after_destroy` - after all background tasks are destroyed
