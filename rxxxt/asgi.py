import os
import codecs, functools, json, mimetypes, pathlib, io
from typing import Any, Callable
from collections.abc import Awaitable, Iterable, MutableMapping, AsyncGenerator
from email.utils import formatdate

BytesLike = bytes | bytearray
ASGIHeaders = Iterable[tuple[BytesLike, BytesLike]]

ASGIScope = MutableMapping[str, Any]
ASGIFnSend = Callable[[MutableMapping[str, Any]], Awaitable[Any]]
ASGIFnReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
ASGIHandler = Callable[[ASGIScope, ASGIFnReceive, ASGIFnSend], Awaitable[Any]]

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

class WebsocketContext(TransportContext):
  def __init__(self, scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    super().__init__(scope, receive, send)
    self._connected = False
    self._accepted = False

  @property
  def connected(self): return self._connected

  @property
  def accepted(self): return self._accepted

  async def setup(self, headers: ASGIHeaders = (), subprotocol: str | None = None):
    if self._connected: raise ConnectionError("Already connected!")
    if self._accepted: raise ConnectionError("Already accepted!")

    event = await self.receive()
    if event["type"] != "websocket.connect": raise ConnectionError("Did not receive connect event!")
    await self.send({ "type": "websocket.accept", "subprotocol": subprotocol, "headers": [ (name.lower(), value) for name, value in headers ] })
    self._connected = self._accepted = True

  async def receive_message(self) -> BytesLike | str:
    if not self._accepted: raise ConnectionError("not accepted!")
    if not self._connected: raise ConnectionError("Not connected!")
    while self._connected:
      event = await self.receive()
      if event["type"] == "websocket.disconnect":
        self._connected = False
        raise ConnectionError("Connection closed!")
      elif event["type"] == "websocket.receive":
        return event.get("bytes", event.get("text"))
    raise ConnectionError("Connection closed!")

  async def send_message(self, data: str | BytesLike):
    if not self._accepted: raise ConnectionError("not accepted!")
    if not self._connected: raise ConnectionError("Not connected!")

    event: dict[str, Any] = { "type": "websocket.send", "bytes": None, "text": None }
    if isinstance(data, str): event["text"] = data
    else: event["bytes"] = data
    await self.send(event)

  async def close(self, code: int = 1000, reason: str = "Normal Closure"):
    if not self._accepted: raise ConnectionError("not accepted!")
    if not self._connected: raise ConnectionError("Not connected!")

    await self.send({ "type": "websocket.close", "code": code, "reason": reason })
    self._connected = False

def content_headers(content_length: int, mime_type: str, charset: str | None = None):
  content_type = mime_type
  if charset is not None: content_type += f"; charset={charset}"
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
    self.add_response_headers(content_headers(len(data), mime_type, "utf-8"))
    await self.response_start(status)
    await self.response_body(data, False)

  async def respond_file(self, path: str | pathlib.Path, mime_type: str | None = None, use_last_modified: bool = False):
    mime_type = mime_type or mimetypes.guess_type(path)[0]
    if mime_type is None: raise ValueError("Unknown mime type!")

    with open(path, "rb") as fd:
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
