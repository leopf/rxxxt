# Getting Started with rxxxt
rxxxt was inspired by React’s component model, but everything renders on the server.  
Think of each `Component` as a React component that already runs inside Python: you return a tree of elements, rxxxt streams the resulting HTML to the browser, and DOM events come back as Python method calls.

## 1. Describe HTML with elements
Just like JSX describes markup in React, the `El`/`VEl` helpers describe HTML in Python. Each helper returns an element object that renders into HTML later.

```html
<section class="card">
  <button disabled>Save</button>
  <input type="text">
</section>
```

```python
from rxxxt import El, VEl

El.section(_class="card", content=[
  El.button(disabled=True, content=["Save"]),
  VEl.input(type="text"),  # void elements come from VEl.*
])
```

If you know how to read HTML, you already know how to read rxxxt elements.

## 2. Build your first component
Components encapsulate logic plus markup, similar to a React component. Override `render` and return any element tree.

```python
from rxxxt import Component, El, Element

class Hero(Component):
  def render(self) -> Element:
    return El.section(_class="hero", content=[
      El.h1(content=["Welcome"]),
      El.p(content=["All HTML comes from this Python function."]),
    ])
```

## 3. Handle events and state
Use `local_state` for reactive data and plain methods for event handlers. Unlike React you do not call `setState`; simply mutate the value and rxxxt re-renders the component. Mount everything with `App`, the equivalent of `createRoot`.

```python
import uvicorn
from rxxxt import Component, El, Element, App, local_state

class Counter(Component):
  count = local_state(int)

  def on_click(self):
    self.count += 1

  def render(self) -> Element:
    return El.div(onclick=self.on_click, content=[
      f"Count: {self.count}"
    ])

app = App(Counter)
uvicorn.run(app)
```

Need debounce/throttle or automatic event payload extraction? Decorate the method with [`@event_handler`](./component.md#events) and set options such as `debounce=300` or `prevent_default=True`.

## 4. Compose components
Components can render other components exactly like React: use them beside HTML nodes, nest them, and pass in constructor arguments or state.

```python
from rxxxt import Component, El, Element, App
import uvicorn

class Card(Component):
  def __init__(self, text: str):
    super().__init__()
    self._text = text

  def render(self) -> Element:
    return El.div(_class="card", content=[f"Happy {self._text}"])

class Dashboard(Component):
  def render(self) -> Element:
    return El.section(_class="wrap", content=[Card("New Year!")])

app = App(Dashboard)
uvicorn.run(app)
```

## 5. Route between pages
`Router` plays the role of React Router. Register callables or components for paths, and read path parameters with `router_params`.

```python
import uvicorn
from rxxxt import App, Component, El, Element, Router, event_handler, local_state, router_params

class ShowWord(Component):
  params = router_params()
  clicks = local_state(int)

  @event_handler()
  def bump(self):
    self.clicks += 1

  def render(self) -> Element:
    return El.div(content=[
      f"Word: '{self.params['word']}' ",
      El.button(onclick=self.bump, content=[f"clicks: {self.clicks}"]),
    ])

router = Router()
router.add_route("/", lambda: El.div(content=["This text renders on /"]))
router.add_route("/hello/{word}", ShowWord)

app = App(router)
uvicorn.run(app)
```

## 6. Load data directly in Python
Because rendering all happens server-side, your components can call databases or internal APIs directly. Coroutines work too: declare `async def render` and `await` inside it.

```python
from rxxxt import Component, El, Element, global_state

class ShoppingList(Component):
  user_id = global_state(int)

  async def render(self) -> Element:
    rows = await sql_select("select item, qty from shopping_list where user_id = ?", self.user_id)
    return El.ul(content=[
      El.li(content=[f"{row['item']} x{row['qty']}"])
      for row in rows
    ])
```

`sql_select` is just a placeholder; plug in your own data access code.

## Next steps
- Learn more about [`Component`](./component.md) lifecycles, events, and decorators.
- Explore [`state.md`](./state.md) for global, context, and shared state helpers.
- Use [`PageBuilder`](./app.md#pagebuilder) to inject CSS, scripts, or custom markup into the document head/body.
- Head over to [`app.md`](./app.md) to see how routing, sessions, and background tasks tie together.
