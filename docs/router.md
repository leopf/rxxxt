# [`Router`](./api.md#rxxxt.router.Router)

Routers can be used to match against url paths and extract parameters.
A router is an [`ElementFactory`](./api.md#rxxxt.elements.ElementFactory) and can be passed directly to the app.

## Adding Routes

Routes can be added with `add_route` supplying the pattern and the element factory for this route.
Alternatively routes can be added using decorators.


```python
from rxxxt import Router, El, App
import uvicorn

router = Router()

def hello_factory():
  return El.div(content=["hello"])

router.add_route("/hello", hello_factory)

@router.route("/world")
def world_factory():
  return El.div(content=["world"])

app = App(router)
uvicorn.run(app)
```

## Route Patterns
The pattern language is simple. You can use any fixed url pattern and it will match exactly that.
To match variables, you can intoduce named parts using braces.

Example: `/{name}/{id}` will match `/project/2` with the parameters `{ "name": "project", "id": "2" }`.

To match accross slashes you may decorate your part with a `*`.

Example: `/{path*}` will match `/project/2` with the parameters `{ "path": "project/2" }`.

## Accessing Parameters

To access the route parameters the `router_params` class field can be used inside components.

```python
from rxxxt import Router, router_params, Component, event_handler, El, Element, App
import uvicorn

class ShowPath(Component):
  params = router_params()

  @event_handler()
  def nav_hello(self): self.context.navigate("/hello")

  @event_handler()
  def nav_world(self): self.context.navigate("/world")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"Word: {self.params.get('word', '-')}"]),
      El.button(onclick=self.nav_hello, content=["nav 'hello'"]),
      El.button(onclick=self.nav_world, content=["nav 'world'"]),
    ])

router = Router()
router.add_route("/{word}", ShowPath)

app = App(router)
uvicorn.run(app)
```
