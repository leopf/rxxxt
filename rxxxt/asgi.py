import codecs
import functools
from io import BytesIO
import json
import mimetypes
import os
import pathlib
from typing import Any, Awaitable, ByteString, Callable, Iterable, Literal, NotRequired, TypedDict

ASGIHeaders = Iterable[tuple[ByteString, ByteString]]

class ASGIScopeBase(TypedDict):
  asgi: dict[Literal["version", "spec_version"], str]
  state: NotRequired[dict[str,Any]]

class LifespanScope(ASGIScopeBase):
  type: Literal["lifespan"]

class TransportScope(ASGIScopeBase):
  http_version: str
  path: str
  raw_path: ByteString | None
  query_string: ByteString | None
  root_path: str
  headers: ASGIHeaders
  client: tuple[str, int]
  server: tuple[str, int]

class HTTPScope(TransportScope):
  type: Literal["http"]
  scheme: Literal["http", "https"]
  method: str

class WebsocketScope(TransportScope):
  type: Literal["websocket"]
  scheme: Literal["ws", "wss"]
  subprotocols: Iterable[str]

ASGIScope = HTTPScope | WebsocketScope | LifespanScope | dict
ASGIFnSend = Callable[[dict], Awaitable[Any]]
ASGIFnReceive = Callable[[], Awaitable[dict]]
ASGIHandler = Callable[[ASGIScope, ASGIFnReceive, ASGIFnSend], Awaitable[Any]]


class TransportContext:
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    self._scope: TransportScope = scope
    self._receive = receive
    self._send = send

  @property
  def path(self): return self._scope["path"]
  @property
  def query_string(self) -> str | None: return None if self._scope["query_string"] is None else self._scope["query_string"].decode("utf-8")
  @property
  def fullpath(self): return (self._scope["raw_path"] or b"").decode("utf-8").split("&", 1)[0]
  @property
  def scope(self) -> TransportScope: return { **self._scope }
  @functools.cached_property
  def headers(self):
    res: dict[str, list[str]] = {}
    for k, v in self._scope["headers"]:
      key = k.decode(errors="ignore").lower()
      res[key] = res.get(key, []) + [v.decode(errors="ignore")] # TODO improve this...
    return res
  @functools.cached_property
  def content_type(self):
    ct = self.headers.get("content-type", None)
    if ct is None or len(ct) == 0: raise ValueError("No content type specified on request!")
    if len(ct) > 1: raise ValueError("More than one content-type was specified!")
    ct = ct[0]
    parts = [ p.strip() for p in ct.split(";") ]
    mime_type = parts[0].lower()
    params = { k.lower(): v for k, v in (tuple(p.split("=") for p in parts[1:] if p.count("=") == 1)) }
    return mime_type, params

  async def _wsend(self, event: dict): await self._send(event)
  async def _wreceive(self) -> dict: return await self._receive()

class WebsocketContext(TransportContext):
  close_reasons = {
    1000: 'Normal Closure', 1001: 'Going Away', 1002: 'Protocol Error',
    1003: 'Unsupported Data', 1004: 'Reserved', 1005: 'No Status Rcvd',
    1006: 'Abnormal Closure', 1007: 'Invalid frame payload data', 1008: 'Policy Violation',
    1009: 'Message too big', 1010: 'Mandatory Ext.', 1011: 'Internal Error',
    1012: 'Service Restart', 1013: 'Try Again Later', 1014: 'Bad Gateway',
    1015: 'TLS Handshake'
  }

  def __init__(self, scope: WebsocketScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected = False
    self._accepted = False
    self._add_accept_headers: list[tuple[ByteString, ByteString]] = []
    self._scope: WebsocketScope

  @property
  def connected(self): return self._connected

  @property
  def accepted(self): return self._accepted

  def add_accept_headers(self, headers: ASGIHeaders): self._add_accept_headers.extend(headers)

  async def messages(self, headers: ASGIHeaders = [], subprotocol: str | None = None):
    await self.accept(headers, subprotocol)
    while self._connected:
      event_type, data = await self.receive()
      if event_type == "message" and data is not None: yield data

  async def accept(self, headers: ASGIHeaders = [], subprotocol: str | None = None):
    if self._accepted: return
    if not self._connected:
      event_type, _ = await self.receive()
      if event_type != "connect": raise RuntimeError(f"Expected 'websocket.connect' event. '{event_type}' received.")
    await self.send_accept(headers, subprotocol)

  async def send_accept(self, headers: ASGIHeaders = [], subprotocol: str | None = None):
    await self._wsend({ "type": "websocket.accept", "subprotocol": subprotocol, "headers": [ (name.lower(), value) for name, value in headers ] })

  async def receive_disconnect(self):
    while True:
      event = await self._wreceive()
      if event.get("type", None) == "websocket.disconnect": return

  async def receive(self) -> tuple[Literal["message", "connect", "disconnect"], str | ByteString | None]:
    event = await self._wreceive()
    if event["type"] == "websocket.connect": return "connect", None
    if event["type"] == "websocket.disconnect": return "disconnect", None
    if event["type"] == "websocket.receive": return "message", event.get("bytes", None) or event.get("text", None)

  async def send_message(self, data: str | ByteString):
    event: dict[str, Any] = { "type": "websocket.send", "bytes": None, "text": None }
    if isinstance(data, str): event["text"] = data
    else: event["bytes"] = data
    await self._wsend(event)

  async def close(self, code: int = 1000, reason: str | None = None):
    self._connected = False
    await self._wsend({ "type": "websocket.close", "code": code, "reason": WebsocketContext.close_reasons.get(code, "") if reason is None else reason })

  async def _wsend(self, event: dict):
    if event["type"] == "websocket.accept":
      self._accepted = True
      event = { **event, "headers": event.get("headers", []) + self._add_accept_headers }
    await super()._wsend(event)

  async def _wreceive(self) -> dict:
    event = await super()._wreceive()
    if event["type"] == "websocket.connect": self._connected = True
    elif event["type"] == "websocket.disconnect": self._connected = False
    return event

class HTTPBodyWriter:
  def __init__(self, send: ASGIFnSend) -> None:
    self._send = send
    self._buffer = BytesIO()

  def write(self, data: ByteString): self._buffer.write(data)
  async def flush(self, close: bool = False):
    await self._send({
      "type": "http.response.body",
      "body": self._buffer.getvalue(),
      "more_body": not close
    })
    self._buffer.seek(0)
    self._buffer.truncate(0)
  async def close(self): await self.flush(True)

class HTTPBodyReader:
  def __init__(self, receive: ASGIFnReceive) -> None:
    self._receive = receive
    self._ended = False

  @property
  def ended(self): return self._ended

  async def read_all(self):
    body = BytesIO()
    while not self._ended: body.write(await self.read())
    return body.getvalue()

  async def read(self):
    event = await self._receive()
    event_type = event.get("type", None)
    if event_type == "http.disconnect": self._ended = True
    if event_type == "http.request":
      self._ended = not event.get("more_body", False)
      return event.get("body", b"")
    return b""

class HTTPContext(TransportContext):
  def __init__(self, scope: HTTPScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected: bool = True
    self._more_request_body: bool = True
    self._more_response_body: bool = True
    self._add_response_headers: list[tuple[ByteString, ByteString]] = []
    self._scope: HTTPScope

  @property
  def connected(self): return self._connected
  @property
  def more_request_body(self): return self._more_request_body
  @property
  def more_response_body(self): return self._more_response_body
  @property
  def method(self): return self._scope["method"]
  @functools.cached_property
  def body(self): return HTTPBodyReader(self._wreceive)

  def add_response_headers(self, headers: ASGIHeaders): self._add_response_headers.extend(headers)

  async def respond_status(self, status: int): await self.respond_text({ 404: "Not found" }.get(status, "-"), status=status)
  async def respond_json(self, json_data: Any, status: int = 200): await self.respond_json_string(json.dumps(json_data), status=status)
  async def respond_json_string(self, json_string: str, status: int = 200): await self.respond_text(json_string, mime_type="application/json", status=status)
  async def respond_json_raw(self, json_data: bytes, status: int = 200, encoding: str = "utf-8"): await self.respond_buffer(status, json_data, mime_type="application/json", charset=encoding)
  async def respond_text(self, text: str, status: int = 200, mime_type: str = "text/plain"): await self.respond_string(status, text, mime_type)
  async def respond_string(self, status: int, text: str, mime_type: str): await self.respond_buffer(status, text.encode("utf-8"), mime_type, "utf-8")
  async def respond_buffer(self, status: int, content: bytes, mime_type: str, charset: str | None = None):
    content_type = mime_type
    if charset is not None: content_type += f"; charset={charset}"
    writer = await self.respond(status, headers=[
      (b"content-length", str(len(content)).encode("utf-8")),
      (b"content-type", content_type.encode("utf-8"))
    ])
    writer.write(content)
    await writer.close()
  async def respond_file(self, path: str | pathlib.Path, status: int = 200, mime_type: str | None = None, buffer_size: int = -1):
    buffer_size = int(buffer_size)
    st = os.stat(path)
    mime_type = mime_type or mimetypes.guess_type(path)[0]
    if mime_type is None: raise ValueError("Unknown mime type!")

    content_type = mime_type
    writer = await self.respond(status, headers=[
      (b"content-length", str(st.st_size).encode("utf-8")),
      (b"content-type", content_type.encode("utf-8"))
    ])

    with open(path, "rb") as fd:
      while len(buf := fd.read(buffer_size)) == buffer_size:
        writer.write(buf)
        await writer.flush()
      writer.write(buf)
      await writer.flush(close=True)
  async def respond(self, status: int, headers: Iterable[tuple[ByteString, ByteString]], trailers: bool = False):
    await self._wsend({
      "type": "http.response.start",
      "status": status,
      "headers": headers,
      "trailers": trailers
    })
    return HTTPBodyWriter(self._wsend)

  async def receive_json(self): return json.loads(await self.receive_json_raw())
  async def receive_json_raw(self): return await self.receive_text({ "application/json" })
  async def receive_text(self, allowed_mime_types: Iterable[str]):
    allowed_mime_types = allowed_mime_types if isinstance(allowed_mime_types, set) else set(allowed_mime_types)
    mime_type, ct_params = self.content_type
    if mime_type not in allowed_mime_types: raise ValueError(f"Mime type '{mime_type}' is not in allowed types!")
    charset = ct_params.get("charset", "utf-8")
    try: decoder = codecs.getdecoder(charset)
    except LookupError: raise ValueError("Invalid content-type encoding!")
    data = await self.body.read_all()
    return decoder(data, "ignore")[0]

  async def _wsend(self, event: dict):
    event_type = event.get("type", None)
    if event_type == "http.response.start": event = { **event, "headers": event.get("headers", []) + self._add_response_headers }
    if event_type == "http.response.body": self._more_response_body = event.get("more_body", False)
    return await super()._wsend(event)
  async def _wreceive(self) -> dict:
    event = await super()._wreceive()
    event_type = event.get("type", None)
    if event_type == "http.disconnect": self._connected = False
    if event_type == "http.request": self._more_request_body = event.get("more_body", False)
    return event
