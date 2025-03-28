# State

State is organized as a key-value store.
In order to associate a state with a session accross multiple requests, a token is created.
The next request of the same session must include the state token, which will then be used to resolve the associated state.

By default the [`JWTStateResolver`](./api.md#rxxxt.state.JWTStateResolver) is used, which transforms the state into a [JWT token](https://jwt.io/introduction), making the server side entirely stateless.

This is handled by the [`StateResolver`](./api.md#rxxxt.state.StateResolver) of the [`App`](./api.md#rxxxt.state.App) (default: [`default_state_resolver`](./api.md#rxxxt.state.default_state_resolver)).

## Conventions

To handle the livetime of state prefixes are used.

- no prefix is global state
- `#` prefix is temporary state, which will be discarded if no longer used
- `!` prefix is protocol state, which holds headers and the location (path + query string). This data will always be present for the components, but is only associated with the token, if actually used

## with Components

There are helpers for defining and using states in Components.
These let you define state variables and access them *almost* like they were native fields.

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
3. **[`context_state`](./api.md#rxxxt.state.context_state)** - which is shared accross components down the tree from the first component that uses it
4. **[`local_state_box`](./api.md#rxxxt.state.local_state_box)** - which is confined to a single component instance, but requires manual updates
```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element, local_state_box

class InputExample(Component):
  text = local_state_box(str)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text.value = value
    self.text.update()

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text", value=self.text.value)
```
5. **[`global_state_box`](./api.md#rxxxt.state.global_state_box)** - which is shared accross the entire application, but requires manual updates
```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element, global_state_box

class InputExample(Component):
  text = global_state_box(str)

  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    self.text.value = value
    self.text.update()

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text", value=self.text.value)
```
6. **[`context_state_box`](./api.md#rxxxt.state.context_state_box)** - which is shared accross components down the tree from the first component that uses it, but requires manual updates
