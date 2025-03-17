# rxxxt (R-3-X-T)
Server side rendered, reactive web applications with python.

**1 dependency (pydantic).**

## Usage
```python
from rxxxt import Component, event_handler, El, Element, App, local_state
import uvicorn

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

app = App(Counter)
uvicorn.run(app)
```

## Usage with FastAPI
```python
from fastapi import FastAPI, Response
import uvicorn
from rxxxt import local_state, Component, event_handler, El, Element, App, PageBuilder, VEl

class Counter(Component):
  count = local_state(int)

  @event_handler()
  def on_click(self): self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[f"Count: {self.count}"])

server = FastAPI()

@server.get("/main.css")
def get_css(): return Response("body { margin: 0; font-family: sans-serif; }", media_type="text/css")

page_builder = PageBuilder()
page_builder.add_header(VEl.link(rel="stylesheet", href="/main.css"))

app = App(Counter, page_layout=page_builder)
server.mount("/", app)
uvicorn.run(server)
```

## Documentation

A rxxxt app is an [ASGI](https://asgi.readthedocs.io/en/latest/specs/main.html) application. It can be used, run and served like any other ASGI application.

### Elements
- `El` - A way to create html elements quickly. Write `El.<tag name>` or `El["<tag name>"]` to create an element with this tag name. You may specify attributes by passing them as key values parameters. The inner content is set by specifying the list `content` with `str | Element` as children.

- `VEl` - A way to create html void elements (like `input`, `meta`, `link` etc.) quickly. Write `VEl.<tag name>` or `VEl["<tag name>"]` to create an element with this tag name. You may specify attributes by passing them as key values parameters. Void elements have no inner content.

- `UnescapedHTMLElement` - Use this to return raw html strings. Example: `UnescapedHTMLElement("<h1>Hello World</h1>")`

- `HTMLFragment` - To create fragments, a container for elements on the same level. Works like react fragments.

- `HTMLVoidElement` - long form of `VEl`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None]` to the constructor
- `HTMLElement` - long form of `El`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None] = {}, content: list[Element | str] = [], key: str | None = None` to the constructor

### Components

To create a component, create a class inheriting from the `Component` class.

You must implement `def render(self) -> Element: ...`. This function will return the elements you would like to be rendered by this component.

You may implement `def on_init(self) -> None | Awaitable[None]: ...`. This will be called when the component is initialized.

Example:
```python
from rxxxt import Component, El, Element

class HelloWorld(Component):
  def render(self) -> Element:
    return El.h1(content=["Hello World"])
```

#### Event handlers

To do anything useful, you will need to handle events. You can do so by creating event handlers.

```python
class HelloButton(Component):
  @event_handler()
  def on_click(self): print("Hello!")

  def render(self) -> Element:
    return El.button(onclick=self.on_click, content=[f"Click me!"])
```


To access browser state, you can access [event](https://developer.mozilla.org/en-US/docs/Web/Events) attributes using the `Annotated` type.

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

Event handlers can be configured with key value parameters complying with the `EventHandlerOptions` model:

```python
class EventHandlerOptions(BaseModel):
  debounce: int | None = None
  throttle: int | None = None
  prevent_default: bool = False
```

You can **debounce** events, making sure to wait a certain amount of time (in ms) until the event is sent to the server and you can **throttle** events making sure they only happen once per interval (in ms). In some cases you may want to **prevent the events default behavior**, like in the case of form submission.

```python
from typing import Annotated
from rxxxt import Component, event_handler, VEl, Element

class InputExample(Component):
  @event_handler(debounce=500)
  def on_input(self, value: Annotated[str, "target.value"]):
    # called after no input event has occured for 500ms
    print("The user entered ", value)

  def render(self) -> Element:
    return VEl.input(oninput=self.on_input, type="text")
```

#### State

Components can have two types of state:
1. **local_state** - which is confined to a single component instance
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

2. **global_state** - which is shared accross the entire application

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
