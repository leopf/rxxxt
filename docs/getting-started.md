# Getting Started with rxxxt
rxxxt is a tool for building purely server-rendered Python web apps. 
Every update is rendered on the server and streamed as HTML, so you do not need to build a frontend or maintain a JSON API.

## HTML, meet `El` (and `VEl`)
The [Elements](./elements.md) reference documents every helper, but the fastest way to grasp it is to compare literal HTML to the `El.*`
calls it maps to. Each helper is just a callable returning an element object.

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
  VEl.input(type="text"),  # VEl is for void elements
])
```

## Counter
This is the exact `examples/counter.py` flow explained in [component.md](./component.md), [state.md](./state.md),
and [app.md](./app.md): `local_state` declares reactive fields.

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

## Nested components
The [Component](./component.md) guide shows how components work. They can be used just like elements. 

```python
import uvicorn
from rxxxt import Component, El, Element, App

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

## Routing
The [Router](./router.md) handles path matching and helps you access the matched parameters with the `router_params` helper.
The root route here is a plain callable (lambda) returning an element, while `/hello/{word}` renders a component.

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
      El.button(onclick=self.bump, content=[
        f"clicks: {self.clicks}"
      ]),
    ])

router = Router()
router.add_route("/", lambda: El.div(content=["This text will be shown on /"]))
router.add_route("/hello/{word}", ShowWord)

app = App(router)
uvicorn.run(app)
```

## External state
Rendering is just Python, so you can load external state mid-render, trade JSON APIs for direct SQL, 
and render table rows from your database directly into HTML. 

See [state.md](./state.md) for more on external and `global_state`.

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

`sql_select` is a fake function, but there are database APIs that look like this, and can be used in place of it.
