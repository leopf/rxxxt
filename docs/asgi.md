# ASGI

rxxxt ships a set of utilities that make it easier to build and compose ASGI applications alongside [`App`](./app.md).

## Transport contexts
- [`TransportContext`](./api.md#rxxxt.asgi.TransportContext) exposes the raw ASGI scope, `receive` and `send` callables plus helpers for common request metadata.
- [`HTTPContext`](./api.md#rxxxt.asgi.HTTPContext) builds on `TransportContext` with helpers such as `respond_text`, streaming `respond_file`, and body readers (`receive_json`, `receive_iter`, ...).
- [`WebsocketContext`](./api.md#rxxxt.asgi.WebsocketContext) provides `setup`, `receive_message`, `send_message`, and `close` helpers while tracking the connection state.

## Handler decorators
- [`http_handler`](./api.md#rxxxt.asgi.http_handler) wraps a coroutine that receives `HTTPContext` and filters for HTTP scopes.
- [`websocket_handler`](./api.md#rxxxt.asgi.websocket_handler) does the same for websocket scopes.
- [`routed_handler`](./api.md#rxxxt.asgi.routed_handler) pairs a simple path pattern (using [`match_path`](./path-matching.md)) with a handler and raises [`ASGINextException`](./api.md#rxxxt.asgi.ASGINextException) so other handlers can try when it does not match.
- [`http_not_found_handler`](./api.md#rxxxt.asgi.http_not_found_handler) is a convenience handler that returns a plain 404 response.

These decorators can be used with a [`Composer`](./api.md#rxxxt.asgi.Composer) instance.

### Example: matching `/favicon.ico`

```python
from rxxxt.asgi import Composer, http_handler, routed_handler, http_not_found_handler

composer = Composer()

@composer.add_handler
@http_handler
@routed_handler("/favicon.ico")
async def favicon(context, params):
  return await context.respond_file("assets/favicon.ico")

composer.add_handler(http_not_found_handler)
```

If the request path does not match `/favicon.ico`, `routed_handler` raises `ASGINextException`, allowing the next handler in the `Composer` chain to run.

## Composer
[`Composer`](./api.md#rxxxt.asgi.Composer) is a lightweight middleware pipeline that works using the ASGI protocol:

```python
from rxxxt.asgi import Composer, http_handler, http_not_found_handler

composer = Composer()

@composer.add_handler
@http_handler
def hello(context):
  return context.respond_text("hello")

composer.add_handler(http_not_found_handler)
```

Handlers that cannot process a scope should raise `ASGINextException` (or call `context.next()` on a `TransportContext`). `Composer` will call the next handler in the chain. Add `http_not_found_handler` as a final fallback to send a simple 404 when no HTTP handler matches.

## Typing helpers
The aliases [`ASGIScope`](./api.md#rxxxt.asgi.ASGIScope), [`ASGIFnReceive`](./api.md#rxxxt.asgi.ASGIFnReceive), [`ASGIFnSend`](./api.md#rxxxt.asgi.ASGIFnSend) and [`ASGIHandler`](./api.md#rxxxt.asgi.ASGIHandler) mirror the ASGI call signatures so middleware you write here works with uvicorn, Starlette/FastAPI, or any other ASGI-compatible stack.
