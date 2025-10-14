# State

State is organized as a key-value store.
In order to associate a state with a session accross multiple requests, a token is created.
The next request of the same session must include the state token, which will then be used to resolve the associated state.

By default the [`JWTStateResolver`](./api.md#rxxxt.state.JWTStateResolver) is used, which transforms the state into a [JWT token](https://jwt.io/introduction), making the server side entirely stateless.

This is handled by the [`StateResolver`](./api.md#rxxxt.state.StateResolver) of the [`App`](./api.md#rxxxt.app.App) (default: [`default_state_resolver`](./api.md#rxxxt.state.default_state_resolver)).

## Conventions

To handle the livetime of state prefixes are used.

- no prefix is global state
- `#` prefix is temporary state, which will be discarded if no longer used
- `!` prefix is protocol state, which holds headers and the location (path + query string). This data will always be present for the components, but is only associated with the token, if actually used

## with Components

There are helpers for defining and using states in Components.
These let you define state variables and access them *almost* like they were native fields.
Descriptors such as `local_state` return the raw value, whereas the `_box` variants hand you a [`StateBox`](./api.md#rxxxt.state.StateBox). A box exposes a `.value` attribute so you can both read and assign; writing to `.value` immediately schedules an update, while mutating the referenced object in-place requires an explicit `.update()` afterwards to keep dependants in sync.

1. **[`local_state`](./api.md#rxxxt.state.local_state)** - which is confined to a single component instance
```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element, local_state

class InputExample(Component):
  text = local_state(str)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text = value

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text", value=self.text)
```
2. **[`global_state`](./api.md#rxxxt.state.global_state)** - which is shared accross the entire application
```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element, global_state

class InputExample(Component):
  text = global_state(str)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text = value

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text", value=self.text)
```
3. **[`context_state`](./api.md#rxxxt.state.context_state)** - which is shared across components down the tree from the first component that uses it
```python
from typing import Annotated
from rxxxt import Component, Element, event_handler, VEl, El, context_state

class Parent(Component):
  text = context_state(str)

  @event_handler()
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text = value

  def render(self) -> Element:
    return El.div(content=[
      VEl.input(oninput=self.on_input, type="text", value=self.text),
      Child(),
    ])

class Child(Component):
  text = context_state(str)

  def render(self) -> Element:
    return El.div(content=[f"Shared text: {self.text}"])
```
4. **[`local_state_box`](./api.md#rxxxt.state.local_state_box)** - which is confined to a single component instance, but requires manual updates
```python
from rxxxt import Component, Element, event_handler, El, local_state_box

class Counter(Component):
  count = local_state_box(int)

  @event_handler()
  def increment(self):
    self.count.value += 1  # assigning to value triggers an update automatically

  def render(self) -> Element:
    return El.div(content=[
      El.button(onclick=self.increment, content=["Add one"]),
      El.span(content=[f"Count: {self.count.value}"]),
    ])
```
5. **[`global_state_box`](./api.md#rxxxt.state.global_state_box)** - which is shared accross the entire application, but requires manual updates
```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element, global_state_box

class InputExample(Component):
  text = global_state_box(str)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text.value = value  # simple assignments propagate automatically

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text", value=self.text.value)
```
6. **[`context_state_box`](./api.md#rxxxt.state.context_state_box)** - which is shared across components down the tree from the first component that uses it, but requires manual updates
```python
from rxxxt import Component, Element, context_state_box, El, event_handler

def default_settings() -> dict[str, int]:
  return {"visits": 0}

class SharedData(Component):
  settings = context_state_box(default_settings)

  @event_handler()
  def add_visit(self):
    self.settings.value["visits"] += 1
    self.settings.update()  # notify that nested data changed in-place

  def render(self) -> Element:
    return El.div(content=[
      El.button(onclick=self.add_visit, content=["Add visit"]),
      El.span(content=[f"Visits: {self.settings.value['visits']}"]),
    ])
```
