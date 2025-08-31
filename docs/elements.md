# Elements

- [`El`](./api.md#rxxxt.elements.El) - A way to create html elements quickly.
  Write `El.<tag name>` or `El["<tag name>"]` to create an element with this tag name.
  You may specify attributes by passing them as key values parameters. The inner content is set by specifying the list `content` with `str | Element` as children.
  Example:
  ```python
  # left underscores are stripped from attribute names
  El.div(_class="button", content=["click me"])
  ```

- [`VEl`](./api.md#rxxxt.elements.VEl) - A way to create html void elements (like `input`, `meta`, `link` etc.) quickly.
  Write `VEl.<tag name>` or `VEl["<tag name>"]` to create an element with this tag name.
  You may specify attributes by passing them as key values parameters. Void elements have no inner content.
  ```python
  # left underscores are stripped from attribute names
  VEl.input(_type="text")
  ```

- [`UnescapedHTMLElement`](./api.md#rxxxt.elements.UnescapedHTMLElement) - Use this to return raw html strings. Example: `UnescapedHTMLElement("<h1>Hello World</h1>")`

- [`HTMLFragment`](./api.md#rxxxt.elements.HTMLFragment) - To create fragments, a container for elements on the same level. Works like react fragments.

- [`HTMLVoidElement`](./api.md#rxxxt.elements.HTMLVoidElement) - long form of `VEl`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None]` to the constructor
- [`HTMLElement`](./api.md#rxxxt.elements.HTMLElement) - long form of `El`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None] = {}, content: Iterable[Element | str] = (), key: str | None = None` to the constructor
