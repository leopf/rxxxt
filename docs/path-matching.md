# Path Matching

[`match_path`](./api.md#rxxxt.helpers.match_path) compares an incoming path against a pattern and returns a dictionary of extracted parameters when it matches, otherwise `None`.

```python
from rxxxt import match_path

if (params := match_path("/projects/{id}", "/projects/42")):
  print(params["id"])  # -> "42"
```

## Pattern syntax

- Plain text segments must match exactly (case-insensitive by default).
- Named captures use `{name}` and are returned in the result dictionary.
- Appending `*` to a part (`{rest*}`) allows matching across multiple path segments.
- Anonymous captures `{}` and `{*}` match without adding a named entry.

Examples:

```python
match_path("/{name}/{id}", "/project/2")
# {'name': 'project', 'id': '2'}

match_path("/{path*}", "/project/2")
# {'path': 'project/2'}
```

Part names must be valid Python identifiers (letters, digits, underscores, and not starting with a digit). Invalid identifiers raise a `ValueError`, so you get fast feedback when defining routes.

## Flags and customisation

`match_path(pattern, path, re_flags=re.IGNORECASE)` accepts any `re` flag value. Pass `re.IGNORECASE | re.VERBOSE` (or others) if you need custom matching behaviour.

## Where it is used

- [`Router`](./router.md) relies on `match_path` to resolve routes and populate `router_params`.
- [`routed_handler`](./asgi.md#handler-decorators) layers the same pattern matching onto ASGI handlers.
