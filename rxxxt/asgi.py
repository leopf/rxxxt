import codecs, functools, json, mimetypes, pathlib, io, asyncio, logging, os, typing
from typing import Any, Callable
from collections.abc import Awaitable, Iterable, MutableMapping, AsyncGenerator
from email.utils import formatdate
from pydantic import ValidationError
from rxxxt.helpers import match_path

BytesLike = bytes | bytearray
ASGIHeaders = Iterable[tuple[BytesLike, BytesLike]]

ASGIScope = MutableMapping[str, Any]
ASGIFnSend = Callable[[MutableMapping[str, Any]], Awaitable[Any]]
ASGIFnReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
ASGIHandler = Callable[[ASGIScope, ASGIFnReceive, ASGIFnSend], Awaitable[Any]]

class ASGINextException(Exception): pass

class TransportContext:
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    self.scope = scope
    self.receive = receive
    self.send = send

  @property
  def path(self): return self.scope["path"]

  @property
  def query_string(self) -> str | None: return None if not self.scope["query_string"] else self.scope["query_string"].decode("utf-8")

  @property
  def fullpath(self): return (self.scope["raw_path"] or b"").decode("utf-8").split("?", 1)[0]

  @functools.cached_property
  def headers(self):
    res: dict[str, tuple[str, ...]] = {}
    for k, v in self.scope["headers"]:
      key = k.decode(errors="ignore").lower()
      res[key] = res.get(key, ()) + (v.decode(errors="ignore"),)
    return res

  @functools.cached_property
  def content_type(self):
    ct = self.headers.get("content-type")
    if ct is None or len(ct) == 0: raise ValueError("No content type specified on request!")
    if len(ct) > 1: raise ValueError("More than one content-type was specified!")
    ct = ct[0]
    parts = [ p.strip() for p in ct.split(";") ]
    mime_type = parts[0].lower()
    params = { k.lower(): v for k, v in (tuple(p.split("=") for p in parts[1:] if p.count("=") == 1)) }
    return mime_type, params

  @property
  def location(self):
    location = self.path
    if self.query_string is not None: location += f"?{self.query_string}"
    return location

  def next(self): raise ASGINextException()

class WebsocketContext(TransportContext):
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected = True

  @property
  def connected(self): return self._connected

  async def setup(self, headers: ASGIHeaders = (), subprotocol: str | None = None):
    event = await self.receive()
    if event["type"] != "websocket.connect": raise ConnectionError("Did not receive connect event!")
    await self.send({ "type": "websocket.accept", "subprotocol": subprotocol, "headers": [ (name.lower(), value) for name, value in headers ] })

  async def receive_message(self) -> BytesLike | str:
    while self._connected:
      event = await self.receive()
      if event["type"] == "websocket.disconnect":
        self._connected = False
        raise ConnectionError("Connection closed!")
      elif event["type"] == "websocket.receive":
        return event.get("bytes", event.get("text"))
    raise ConnectionError("Connection closed!")

  async def send_message(self, data: str | BytesLike):
    if not self._connected: raise ConnectionError("Not connected!")
    event: dict[str, Any] = { "type": "websocket.send", "bytes": None, "text": None }
    if isinstance(data, str): event["text"] = data
    else: event["bytes"] = data
    await self.send(event)

  async def close(self, code: int = 1000, reason: str = "Normal Closure"):
    await self.send({ "type": "websocket.close", "code": code, "reason": reason })
    self._connected = False

def content_headers(content_length: int, content_type: str):
  return [
    (b"content-length", str(content_length).encode("utf-8")),
    (b"content-type", content_type.encode("utf-8"))
  ]

class HTTPContext(TransportContext):
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._response_headers: list[tuple[BytesLike, BytesLike]] = []

  @property
  def method(self): return self.scope["method"]

  def add_response_headers(self, headers: ASGIHeaders): self._response_headers.extend(headers)

  async def response_start(self, status: int, trailers: bool = False):
    await self.send({
      "type": "http.response.start",
      "status": status,
      "headers": self._response_headers,
      "trailers": trailers
    })

  async def response_body(self, data: BytesLike, more_body: bool):
    await self.send({
      "type": "http.response.body",
      "body": data,
      "more_body": more_body
    })

  async def respond_text(self, text: str, status: int = 200, mime_type: str = "text/plain"):
    data = text.encode("utf-8")
    self.add_response_headers(content_headers(len(data), mime_type + "; charset=utf-8"))
    await self.response_start(status)
    await self.response_body(data, False)

  async def respond_file(self, path: str | pathlib.Path, mime_type: str | None = None, handle_404: bool = False, use_last_modified: bool = False):
    mime_type = mime_type or mimetypes.guess_type(path)[0]
    if mime_type is None: raise ValueError("Unknown mime type!")
    ppath = pathlib.Path(path)
    if handle_404 and not ppath.exists():
      return await self.respond_text("not found", 404)

    with open(ppath, "rb") as fd:
      fd_stat = os.stat(fd.fileno())

      if use_last_modified:
        last_modified = formatdate(fd_stat.st_mtime, usegmt=True).encode()
        self.add_response_headers([ (b"Last-Modified", last_modified) ])
        if (last_modified,) == self.headers.get("If-Modified-Since", None):
          await self.response_start(304)
          await self.response_body(b"", False)
          return

      self.add_response_headers(content_headers(fd_stat.st_size, mime_type))
      await self.response_start(200)
      while len(data := fd.read(1_000_000)) != 0:
        await self.response_body(data, fd.tell() != fd_stat.st_size)

  async def receive_json(self): return json.loads(await self.receive_json_raw())

  async def receive_json_raw(self): return await self.receive_text({ "application/json" })

  async def receive_text(self, allowed_mime_types: Iterable[str]):
    allowed_mime_types = allowed_mime_types if isinstance(allowed_mime_types, set) else set(allowed_mime_types)
    mime_type, ct_params = self.content_type
    if mime_type not in allowed_mime_types: raise ValueError(f"Mime type '{mime_type}' is not in allowed types!")
    charset = ct_params.get("charset", "utf-8")
    try: decoder = codecs.getdecoder(charset)
    except LookupError: raise ValueError("Invalid content-type encoding!")
    data = await self.receive_bytes()
    return decoder(data, "ignore")[0]

  async def receive_bytes(self) -> bytes:
    stream = io.BytesIO()
    async for chunk in self.receive_iter():
      _ = stream.write(chunk)
    return stream.getvalue()

  async def receive_iter(self) -> AsyncGenerator[bytes, Any]:
    while True:
      event = await self.receive()
      event_type = event.get("type")
      if event_type == "http.request":
        yield event.get("body", b"")
        if not event.get("more_body", False): return
      elif event_type == "http.disconnect": return

def http_handler(fn: Callable[[HTTPContext], Awaitable[Any]]):
  async def _inner(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] != "http": raise ASGINextException()
    return await fn(HTTPContext(scope, receive, send))
  return _inner

def websocket_handler(fn: Callable[[WebsocketContext], Awaitable[Any]]):
  async def _inner(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    if scope["type"] != "websocket": raise ASGINextException()
    return await fn(WebsocketContext(scope, receive, send))
  return _inner

CTXT = typing.TypeVar("CTXT", bound=TransportContext)
def routed_handler(pattern: str):
  def _inner(fn: Callable[[CTXT, dict[str, str]], Awaitable[Any]]) -> Callable[[CTXT], Awaitable[Any]]:
    async def _inner_inner(context: CTXT) -> Any:
      if (match:=match_path(pattern, context.path)) is None: context.next()
      return await fn(context, match)
    return _inner_inner
  return _inner

@http_handler
async def http_not_found_handler(context: HTTPContext):
  await context.respond_text("not found", 404)

class Composer:
  def __init__(self) -> None:
    self._handlers: list[ASGIHandler] = []

  def add_handler(self, handler: ASGIHandler):
    self._handlers.append(handler)
    return handler

  async def __call__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> Any:
    try:
      for handler in self._handlers:
        try: return await handler(scope, receive, send)
        except ASGINextException: pass
    except asyncio.CancelledError: raise
    except BaseException as e:
      logging.debug("asgi error", exc_info=True, stack_info=True)
      if scope["type"] == "websocket":
        return await self._ws_error_handler(WebsocketContext(scope, receive, send), e)
      if scope["type"] == "http":
        return await self._http_error_handler(HTTPContext(scope, receive, send), e)

  async def _http_error_handler(self, context: HTTPContext, exception: BaseException):
    if isinstance(exception, (ValueError, ValidationError)):
      return await context.respond_text("bad request", 400)
    else:
      return await context.respond_text("internal server error", 500)

  async def _ws_error_handler(self, context: WebsocketContext, _exception: BaseException):
    await context.close(1011, "Internal error")
