# [`App`](./api.md#rxxxt.app.App)

A rxxxt app is an [ASGI](https://asgi.readthedocs.io/en/latest/specs/main.html) application. It can be used, run and served like any other ASGI application.

Apps can be created by simply passing an element factory (a function producing an element) to [`App`](./api.md#rxxxt.app.App).

Let's write a "Hello World!" app:
```python
from rxxxt import App, El
import uvicorn

def element_factory():
  return El.div(content=["Hello World!"])

app = App(element_factory)
uvicorn.run(app)
```

Anything that returns an element, if called can be used as an `element_factory`.
Like this "Hello World" component:

```python
from rxxxt import App, El, Component
import uvicorn

class HelloWorld(Component):
  def render(self) -> Element:
    return El.div(content=["Hello World"])

app = App(HelloWorld)
uvicorn.run(app)
```

In addition to the element factory, a `state_resolver` (see [State](./state.md)), `page_factory`, and `config` (an [`AppConfig`](./api.md#rxxxt.session.AppConfig)) can be passed to `App`.

## AppConfig

- `enable_web_socket_state_updates`: set to `True` when websocket pushes should include a refreshed state token so the client can keep its `StateResolver` data after the socket closes or falls back to HTTP. Leave it `False` when the websocket never needs to persist state beyond its lifetime.
- `disable_http_update_retry`: set to `True` to disable resending events over HTTP when the response indicates the update is stale (new events arrived while the request was processing).

## Page Factory

A page factory is a function receiving

- a header element,
- a content element,
- and a body_end element

returning an element that represents the html page structure.

Take a look at the [`default_page`](./api.md#rxxxt.page.default_page) as an example:
```python
def default_page(header: Element, content: Element, body_end: Element):
  return HTMLFragment([
    VEl["!DOCTYPE"](html=None),
    El.html(content=[
      El.head(content=[
        VEl.meta(charset="UTF-8"),
        VEl.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        header
      ]),
      El.body(content=[
        content,
        body_end
      ])
    ])
  ])
```

### [`PageBuilder`](./api.md#rxxxt.page.PageBuilder)
A page builder can be used to modify the contents of a page.
An instance of `PageBuilder` is a `page_factory`.

Using the utility methods, the contents of header, content and body_end can be extended.
Let's add a stylesheet to the header:
```python
page_builder = PageBuilder()
page_builder.add_stylesheet("/assets/main.css")
app = App(element_factory, page_factory=page_builder)
```

Scripts that should run after the main content is rendered can be appended through `add_body_end`.
```python
page_builder.add_body_end(El.script(content=[UnescapedHTMLElement("""
console.log("hello world");
""")]))
```
