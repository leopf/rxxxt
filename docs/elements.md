# Elements

- [`Element`](./api.md#rxxxt.elements.Element) - Abstract base for every renderable element. Implement `tonode` to describe how the element expands in the tree.
- [`CustomAttribute`](./api.md#rxxxt.elements.CustomAttribute) - Base class for special attributes that expand into real HTML attributes at render time.
- [`ElementContent`](./api.md#rxxxt.elements.ElementContent) - Sequence of child elements or strings accepted by most element constructors.
- [`HTMLAttributeValue`](./api.md#rxxxt.elements.HTMLAttributeValue) / [`HTMLAttributes`](./api.md#rxxxt.elements.HTMLAttributes) - Accepted attribute shapes for HTML elements. Non-string primitives are converted.
- [`lazy_element`](./api.md#rxxxt.elements.lazy_element) - Wrap a factory that receives the current `Context` when the element is rendered.
- [`TextElement`](./api.md#rxxxt.elements.TextElement) - Escapes text so it can be safely inserted into the DOM tree.
- [`ElementFactory`](./api.md#rxxxt.elements.ElementFactory) - Protocol for callables that create elements.
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
- [`KeyedElement`](./api.md#rxxxt.elements.KeyedElement) - Sets the rendering key of an element.
- [`WithRegistered`](./api.md#rxxxt.elements.WithRegistered) - Registeres values for its child. Intended to be used in combination with `self.context.registered(...)`.

- [`HTMLVoidElement`](./api.md#rxxxt.elements.HTMLVoidElement) - long form of `VEl`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None]` to the constructor
- [`HTMLElement`](./api.md#rxxxt.elements.HTMLElement) - long form of `El`, pass `tag: str, attributes: dict[str, str | CustomAttribute | None] = {}, content: Iterable[Element | str] = (), key: str | None = None` to the constructor
- [`class_map`](./api.md#rxxxt.elements.class_map) - Turn a `dict[str, bool]` into a space separated class string.
- [`css_extend`](./api.md#rxxxt.elements.css_extend) - Merge additional `class` / `style` values into an attribute dict.
