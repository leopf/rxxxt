import asyncio
import base64
import dataclasses
import hashlib
import http.client
import logging
import signal
import ssl
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Protocol, cast
from rxxxt.asgi import ASGIHandler, ASGIScope

__all__ = ["HTTPServer", "ServerConfig"]

WS_GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
CHUNK_READ = 65536

_LOG_LEVELS: dict[str, int] = {
  "debug": logging.DEBUG,
  "info": logging.INFO,
  "warning": logging.WARNING,
  "error": logging.ERROR,
  "critical": logging.CRITICAL,
}

@dataclasses.dataclass(frozen=True, slots=True)
class ServerConfig:
  host: str = "127.0.0.1"
  port: int = 8000
  ssl_context: ssl.SSLContext | None = None
  log_level: str = "info"
  lifespan_timeout: float = 30.0
  ws_max_size: int = 1 << 20
  keepalive_timeout: float = 5.0
  max_request_size: int = 1 << 24
  request_header_limit: int = 100
  extensions: tuple[str, ...] = ("websocket.http.response",)

class _BadRequest(Exception):
  pass

class _BadVersion(Exception):
  pass

def _ev_str(e: Mapping[str, object], key: str) -> str | None:
  v = e.get(key)
  if v is None:
    return None
  if isinstance(v, str):
    return v
  raise ValueError(f"{key} must be a str")

def _ev_int(e: Mapping[str, object], key: str, default: int = 0) -> int:
  v = e.get(key, default)
  if isinstance(v, bool):
    raise ValueError(f"{key} must be an int, not bool")
  if isinstance(v, int):
    return v
  raise ValueError(f"{key} must be an int")

def _ev_bool(e: Mapping[str, object], key: str, default: bool = False) -> bool:
  v = e.get(key, default)
  if isinstance(v, bool):
    return v
  raise ValueError(f"{key} must be a bool")

def _ev_bytes(e: Mapping[str, object], key: str, default: bytes = b"") -> bytes:
  v = e.get(key, default)
  if isinstance(v, (bytes, bytearray)):
    return bytes(v)
  raise ValueError(f"{key} must be bytes")

def _ev_opt_str(e: Mapping[str, object], key: str) -> str | None:
  v = e.get(key)
  if v is None:
    return None
  if isinstance(v, str):
    return v
  raise ValueError(f"{key} must be a str or None")

def _ev_headers(e: Mapping[str, object]) -> list[tuple[bytes, bytes]]:
  v = e.get("headers", [])
  if not isinstance(v, Sequence) or isinstance(v, (str, bytes, bytearray)):
    raise ValueError("headers must be a sequence")
  out: list[tuple[bytes, bytes]] = []
  for item in v:
    if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)):
      raise ValueError("header must be a sequence")
    if len(item) != 2:
      raise ValueError("header must be a 2-tuple")
    n, val = item[0], item[1]
    if not isinstance(n, (bytes, bytearray)) or not isinstance(val, (bytes, bytearray)):
      raise ValueError("header name/value must be bytes")
    out.append((bytes(n), bytes(val)))
  return out

def _reason(status: int) -> str:
  return http.client.responses.get(status, "Unknown")

def _split_target(target: bytes) -> tuple[bytes, bytes]:
  if target == b"*":
    return b"*", b""
  if target.startswith(b"/"):
    p, _, q = target.partition(b"?")
    return p, q
  s = target.decode("latin-1", "replace")
  u = urllib.parse.urlsplit(s)
  raw = (u.path or "/").encode("latin-1")
  return raw, u.query.encode("latin-1")

def _decode_path(raw: bytes) -> str:
  if raw == b"*":
    return "*"
  return urllib.parse.unquote_to_bytes(raw).decode("utf-8", "replace")

def _ws_accept_key(key: bytes) -> bytes:
  return base64.b64encode(hashlib.sha1(key + WS_GUID).digest())

def _encode_frame(opcode: int, payload: bytes, fin: bool = True) -> bytes:
  b0 = (0x80 if fin else 0) | (opcode & 0x0f)
  n = len(payload)
  if n < 126:
    head = bytes((b0, n))
  elif n < 65536:
    head = bytes((b0, 126)) + n.to_bytes(2, "big")
  else:
    head = bytes((b0, 127)) + n.to_bytes(8, "big")
  return head + payload

async def _read_frame(reader: asyncio.StreamReader) -> tuple[bool, int, int, bool, bytes]:
  h = await reader.readexactly(2)
  b0, b1 = h[0], h[1]
  fin = bool(b0 & 0x80)
  rsv = b0 & 0x70
  opcode = b0 & 0x0f
  masked = bool(b1 & 0x80)
  length = b1 & 0x7f
  if length == 126:
    length = int.from_bytes(await reader.readexactly(2), "big")
  elif length == 127:
    length = int.from_bytes(await reader.readexactly(8), "big")
  mask = await reader.readexactly(4) if masked else b""
  payload = await reader.readexactly(length) if length else b""
  if masked:
    payload = bytes(payload[i] ^ mask[i & 3] for i in range(len(payload)))
  return fin, rsv, opcode, masked, payload

async def _read_headers(reader: asyncio.StreamReader, limit: int) -> list[tuple[bytes, bytes]]:
  headers: list[tuple[bytes, bytes]] = []
  while True:
    line = await reader.readline()
    if not line:
      raise _BadRequest("unexpected EOF in headers")
    if line in (b"\r\n", b"\n"):
      break
    if line[-1:] != b"\n":
      raise _BadRequest("header line too long")
    stripped = line.rstrip(b"\r\n")
    if stripped[:1] in (b" ", b"\t"):
      if not headers:
        raise _BadRequest("invalid header continuation")
      n, v = headers[-1]
      headers[-1] = (n, v + b" " + stripped.strip())
      continue
    name, sep, value = stripped.partition(b":")
    if not sep:
      raise _BadRequest("invalid header line")
    headers.append((name.lower().strip(), value.strip()))
    if len(headers) > limit:
      raise _BadRequest("too many headers")
  return headers

async def _write_error_response(writer: asyncio.StreamWriter, hv: str, status: int, message: str) -> None:
  body = message.encode("utf-8") + b"\n"
  head = f"HTTP/{hv} {status} {_reason(status)}\r\n".encode("latin-1")
  head += b"content-type: text/plain; charset=utf-8\r\n"
  head += b"content-length: " + str(len(body)).encode("ascii") + b"\r\n"
  head += b"connection: close\r\n\r\n"
  writer.write(head + body)
  await writer.drain()

def _get_header(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
  for k, v in headers:
    if k == name:
      return v
  return None

def _get_headers_all(headers: list[tuple[bytes, bytes]], name: bytes) -> list[bytes]:
  return [v for k, v in headers if k == name]

class _HttpContext:
  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, hv: str, content_length: int | None, chunked: bool, force_close: bool, config: ServerConfig) -> None:
    self._reader: asyncio.StreamReader = reader
    self._writer: asyncio.StreamWriter = writer
    self._hv: str = hv
    self._content_length: int | None = content_length
    self._chunked: bool = chunked
    self._has_body: bool = chunked or (content_length is not None)
    self._remaining: int = content_length or 0
    self._force_close: bool = force_close
    self._config: ServerConfig = config
    self._body_done: bool = False
    self._body_disconnected: bool = False
    self._resp_started: bool = False
    self._resp_head_sent: bool = False
    self._resp_complete: bool = False
    self._resp_status: int = 200
    self._resp_headers: list[tuple[bytes, bytes]] = []
    self._framing: str | None = None
    self.close_after: bool = False
    self._trailers: bool = False
    self._trailers_started: bool = False

  @property
  def response_head_sent(self) -> bool:
    return self._resp_head_sent

  @property
  def response_complete(self) -> bool:
    return self._resp_complete

  async def receive(self) -> ASGIScope:
    if self._body_done or self._body_disconnected:
      return {"type": "http.disconnect"}
    try:
      data, more = await self._read_body_chunk()
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
      self._body_disconnected = True
      return {"type": "http.disconnect"}
    if not more:
      self._body_done = True
    return {"type": "http.request", "body": data, "more_body": more}

  async def _read_body_chunk(self) -> tuple[bytes, bool]:
    if not self._has_body:
      return b"", False
    if self._chunked:
      size_line = await self._reader.readline()
      if not size_line:
        raise asyncio.IncompleteReadError(b"", None)
      size_field = size_line.rstrip(b"\r\n").split(b";", 1)[0].strip()
      try:
        size = int(size_field, 16)
      except ValueError:
        raise _BadRequest("bad chunk size")
      if size == 0:
        while True:
          t = await self._reader.readline()
          if t in (b"\r\n", b"\n", b""):
            break
        return b"", False
      if size > self._config.max_request_size:
        raise _BadRequest("chunk too large")
      data = await self._reader.readexactly(size)
      _ = await self._reader.readexactly(2)
      return data, True
    if self._remaining <= 0:
      return b"", False
    to_read = min(self._remaining, CHUNK_READ)
    data = await self._reader.read(to_read)
    if not data:
      raise asyncio.IncompleteReadError(b"", to_read)
    self._remaining -= len(data)
    return data, self._remaining > 0

  async def drain_body(self) -> None:
    while not self._body_done and not self._body_disconnected:
      try:
        _data, more = await self._read_body_chunk()
      except (asyncio.IncompleteReadError, ConnectionError, OSError, _BadRequest):
        self._body_disconnected = True
        return
      if not more:
        self._body_done = True
        return

  async def send(self, event: Mapping[str, object]) -> None:
    t = _ev_str(event, "type")
    if t == "http.response.start":
      if self._resp_started:
        raise ValueError("response already started")
      self._resp_status = _ev_int(event, "status", 200)
      self._resp_headers = _ev_headers(event)
      self._resp_started = True
      self._trailers = _ev_bool(event, "trailers", False)
    elif t == "http.response.body":
      if not self._resp_started:
        raise ValueError("body before response start")
      body = _ev_bytes(event, "body", b"")
      more = _ev_bool(event, "more_body", False)
      if not self._resp_head_sent:
        await self._send_head()
      await self._write_body_chunk(body, more)
      if not more and not self._trailers:
        self._resp_complete = True
    elif t == "http.response.trailers":
      if not self._resp_started or not self._trailers:
        raise ValueError("trailers not expected")
      headers = _ev_headers(event)
      await self._handle_trailers(headers, _ev_bool(event, "more_trailers", False))
    else:
      raise ValueError(f"unknown http send event: {t}")

  async def _send_head(self) -> None:
    if self._force_close:
      self.close_after = True
    out: list[tuple[bytes, bytes]] = []
    has_cl = False
    for name, value in self._resp_headers:
      lname = name.lower()
      if lname == b"transfer-encoding":
        continue
      if lname == b"connection":
        continue
      if lname == b"content-length":
        has_cl = True
      out.append((name, value))
    if self._trailers:
      self._framing = "chunked"
      out.append((b"transfer-encoding", b"chunked"))
      has_cl = False
    elif has_cl:
      self._framing = "content-length"
    elif self._hv == "1.1":
      self._framing = "chunked"
      out.append((b"transfer-encoding", b"chunked"))
    else:
      self._framing = "close"
      self.close_after = True
    out.append((b"connection", b"close" if self.close_after else b"keep-alive"))
    lines = [f"HTTP/{self._hv} {self._resp_status} {_reason(self._resp_status)}".encode("latin-1")]
    lines += [name + b": " + value for name, value in out]
    lines.append(b"")
    lines.append(b"")
    self._writer.write(b"\r\n".join(lines))
    await self._writer.drain()
    self._resp_head_sent = True

  async def _write_body_chunk(self, body: bytes, more: bool) -> None:
    if self._framing == "chunked":
      if body:
        self._writer.write(f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n")
      if not more and not self._trailers:
        self._writer.write(b"0\r\n\r\n")
      await self._writer.drain()
    elif self._framing == "content-length":
      if body:
        self._writer.write(body)
        await self._writer.drain()
    else:
      if body:
        self._writer.write(body)
        await self._writer.drain()

  async def _handle_trailers(self, headers: list[tuple[bytes, bytes]], more_trailers: bool) -> None:
    if not self._trailers_started:
      self._writer.write(b"0\r\n")
      self._trailers_started = True
    for name, value in headers:
      self._writer.write(name + b": " + value + b"\r\n")
    if not more_trailers:
      self._writer.write(b"\r\n")
      self._resp_complete = True
    await self._writer.drain()

  async def send_error_response(self, status: int, message: str) -> None:
    body = message.encode("utf-8") + b"\n"
    self._resp_status = status
    self._resp_headers = [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", str(len(body)).encode("ascii"))]
    self._resp_started = True
    await self._send_head()
    self._writer.write(body)
    if self._framing == "chunked":
      self._writer.write(b"0\r\n\r\n")
    await self._writer.drain()
    self._resp_complete = True

class _WsContext:
  def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, config: ServerConfig, accept_key: bytes) -> None:
    self._reader: asyncio.StreamReader = reader
    self._writer: asyncio.StreamWriter = writer
    self._config: ServerConfig = config
    self._accept_key: bytes = accept_key
    self._accepted: bool = False
    self._closed: bool = False
    self._http_responded: bool = False
    self._recv_queue: asyncio.Queue[ASGIScope] = asyncio.Queue()
    self._recv_queue.put_nowait({"type": "websocket.connect"})
    self._reader_task: asyncio.Task[None] | None = None
    self._frag: tuple[int, bytearray] | None = None
    self._resp_started: bool = False
    self._resp_head_sent: bool = False
    self._resp_status: int = 200
    self._resp_headers: list[tuple[bytes, bytes]] = []

  async def receive(self) -> ASGIScope:
    return await self._recv_queue.get()

  async def send(self, event: Mapping[str, object]) -> None:
    t = _ev_str(event, "type")
    if t == "websocket.accept":
      await self._accept(event)
    elif t == "websocket.send":
      await self._send_msg(event)
    elif t == "websocket.close":
      await self._close(event)
    elif t == "websocket.http.response.start":
      await self._ws_http_start(event)
    elif t == "websocket.http.response.body":
      await self._ws_http_body(event)
    else:
      raise ValueError(f"unknown websocket send event: {t}")

  async def _accept(self, event: Mapping[str, object]) -> None:
    if self._accepted:
      raise ValueError("already accepted")
    if self._closed:
      raise OSError("connection closed")
    subprotocol = _ev_opt_str(event, "subprotocol")
    lines = [b"HTTP/1.1 101 Switching Protocols", b"Upgrade: websocket", b"Connection: Upgrade", b"Sec-WebSocket-Accept: " + self._accept_key]
    if subprotocol is not None:
      lines.append(b"Sec-WebSocket-Protocol: " + subprotocol.encode("latin-1"))
    for name, value in _ev_headers(event):
      if name.lower() == b"sec-websocket-protocol":
        continue
      lines.append(name + b": " + value)
    lines.append(b"")
    lines.append(b"")
    self._writer.write(b"\r\n".join(lines))
    await self._writer.drain()
    self._accepted = True
    self._reader_task = asyncio.create_task(self._read_loop())

  async def _send_msg(self, event: Mapping[str, object]) -> None:
    if not self._accepted:
      raise ValueError("websocket not accepted")
    if self._closed:
      raise OSError("connection closed")
    text = event.get("text")
    data = event.get("bytes")
    if text is not None:
      if not isinstance(text, str):
        raise ValueError("text must be a str")
      payload = text.encode("utf-8")
      opcode = 0x1
    elif data is not None:
      if not isinstance(data, (bytes, bytearray)):
        raise ValueError("bytes must be bytes")
      payload = bytes(data)
      opcode = 0x2
    else:
      raise ValueError("websocket.send requires text or bytes")
    self._writer.write(_encode_frame(opcode, payload))
    await self._writer.drain()

  async def _close(self, event: Mapping[str, object]) -> None:
    code = _ev_int(event, "code", 1000)
    reason = _ev_opt_str(event, "reason") or ""
    if not self._accepted:
      body = b"Forbidden\n"
      head = b"HTTP/1.1 403 Forbidden\r\ncontent-length: " + str(len(body)).encode("ascii") + b"\r\nconnection: close\r\n\r\n"
      self._writer.write(head + body)
      await self._writer.drain()
      self._closed = True
      return
    payload = code.to_bytes(2, "big") + reason.encode("utf-8")
    self._writer.write(_encode_frame(0x8, payload))
    await self._writer.drain()
    self._closed = True

  async def _ws_http_start(self, event: Mapping[str, object]) -> None:
    if self._accepted:
      raise ValueError("already accepted")
    self._resp_status = _ev_int(event, "status", 200)
    self._resp_headers = _ev_headers(event)
    self._resp_started = True

  async def _ws_http_body(self, event: Mapping[str, object]) -> None:
    if not self._resp_started:
      raise ValueError("body before response start")
    body = _ev_bytes(event, "body", b"")
    more = _ev_bool(event, "more_body", False)
    if not self._resp_head_sent:
      lines = [f"HTTP/1.1 {self._resp_status} {_reason(self._resp_status)}".encode("latin-1")]
      for name, value in self._resp_headers:
        if name.lower() in (b"transfer-encoding", b"connection"):
          continue
        lines.append(name + b": " + value)
      lines.append(b"connection: close")
      lines.append(b"")
      lines.append(b"")
      self._writer.write(b"\r\n".join(lines))
      self._resp_head_sent = True
    if body:
      self._writer.write(body)
    await self._writer.drain()
    if not more:
      self._http_responded = True
      self._closed = True

  async def _read_loop(self) -> None:
    try:
      while True:
        fin, rsv, opcode, masked, payload = await _read_frame(self._reader)
        if rsv:
          await self._fail(1002, "rsv not zero")
          return
        if not masked:
          await self._fail(1002, "client frame not masked")
          return
        if opcode == 0x9:
          self._writer.write(_encode_frame(0xA, payload[:125]))
          await self._writer.drain()
          continue
        if opcode == 0xA:
          continue
        if opcode == 0x8:
          code, reason = self._parse_close(payload)
          try:
            self._writer.write(_encode_frame(0x8, payload if len(payload) >= 2 else b""))
            await self._writer.drain()
          except (ConnectionError, OSError):
            pass
          await self._recv_queue.put({"type": "websocket.disconnect", "code": code if code is not None else 1005, "reason": reason})
          self._closed = True
          return
        if opcode in (0x1, 0x2):
          if fin:
            await self._deliver(opcode, payload)
          else:
            if self._frag is not None:
              await self._fail(1002, "nested fragment")
              return
            self._frag = (opcode, bytearray(payload))
            if len(self._frag[1]) > self._config.ws_max_size:
              await self._fail(1009, "message too big")
              return
          continue
        if opcode == 0x0:
          if self._frag is None:
            await self._fail(1002, "continuation without fragment")
            return
          self._frag[1].extend(payload)
          if len(self._frag[1]) > self._config.ws_max_size:
            await self._fail(1009, "message too big")
            return
          if fin:
            op, data = self._frag
            self._frag = None
            await self._deliver(op, bytes(data))
          continue
        await self._fail(1002, "unknown opcode")
        return
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
      if not self._closed:
        await self._recv_queue.put({"type": "websocket.disconnect", "code": 1005, "reason": ""})
        self._closed = True

  async def _deliver(self, opcode: int, payload: bytes) -> None:
    if len(payload) > self._config.ws_max_size:
      await self._fail(1009, "message too big")
      return
    if opcode == 0x1:
      try:
        text = payload.decode("utf-8")
      except UnicodeDecodeError:
        await self._fail(1007, "invalid utf-8")
        return
      await self._recv_queue.put({"type": "websocket.receive", "text": text, "bytes": None})
    else:
      await self._recv_queue.put({"type": "websocket.receive", "text": None, "bytes": payload})

  async def _fail(self, code: int, reason: str = "") -> None:
    try:
      payload = code.to_bytes(2, "big") + reason.encode("utf-8")
      self._writer.write(_encode_frame(0x8, payload))
      await self._writer.drain()
    except (ConnectionError, OSError):
      pass
    await self._recv_queue.put({"type": "websocket.disconnect", "code": code, "reason": reason})
    self._closed = True

  @staticmethod
  def _parse_close(payload: bytes) -> tuple[int | None, str]:
    if len(payload) == 0:
      return None, ""
    if len(payload) == 1:
      return 1002, ""
    code = int.from_bytes(payload[:2], "big")
    try:
      reason = payload[2:].decode("utf-8")
    except UnicodeDecodeError:
      reason = payload[2:].decode("utf-8", "replace")
    return code, reason

  async def finalize(self) -> None:
    if self._http_responded:
      pass
    elif not self._accepted and not self._closed:
      body = b"Forbidden\n"
      head = b"HTTP/1.1 403 Forbidden\r\ncontent-length: " + str(len(body)).encode("ascii") + b"\r\nconnection: close\r\n\r\n"
      try:
        self._writer.write(head + body)
        await self._writer.drain()
      except (ConnectionError, OSError):
        pass
      self._closed = True
    elif self._accepted and not self._closed:
      try:
        self._writer.write(_encode_frame(0x8, (1001).to_bytes(2, "big") + b""))
        await self._writer.drain()
      except (ConnectionError, OSError):
        pass
      self._closed = True
    if self._reader_task is not None and not self._reader_task.done():
      _ = self._reader_task.cancel()
      try:
        await self._reader_task
      except (asyncio.CancelledError, Exception):
        pass

class _GetLifespanState(Protocol):
  def __call__(self) -> dict[str, object] | None: ...

class _Connection:
  def __init__(self, app: ASGIHandler, config: ServerConfig, log: logging.Logger, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, get_lifespan_state: _GetLifespanState) -> None:
    self._app: ASGIHandler = app
    self._config: ServerConfig = config
    self._log: logging.Logger = log
    self._reader: asyncio.StreamReader = reader
    self._writer: asyncio.StreamWriter = writer
    self._get_lifespan_state: _GetLifespanState = get_lifespan_state
    peer = cast("tuple[str, int] | None", writer.get_extra_info("peername"))
    sock = cast("tuple[str, int] | None", writer.get_extra_info("sockname"))
    self._client: list[str | int] | None = [peer[0], peer[1]] if peer is not None and len(peer) >= 2 else None
    self._server_addr: list[str | int] | None = [sock[0], sock[1]] if sock is not None and len(sock) >= 2 else None
    self._ssl: bool = config.ssl_context is not None

  async def run(self) -> None:
    hv = "1.1"
    try:
      while True:
        try:
          req = await self._read_request()
        except _BadRequest as e:
          await _write_error_response(self._writer, hv, 400, str(e))
          return
        except _BadVersion:
          await _write_error_response(self._writer, hv, 505, "HTTP Version Not Supported")
          return
        if req is None:
          return
        method, target, hv, headers = req
        upgrade = _get_header(headers, b"upgrade")
        if upgrade is not None and upgrade.lower() == b"websocket" and hv == "1.1":
          await self._handle_ws(method, target, headers)
          return
        keep = await self._handle_http(method, target, hv, headers)
        if not keep:
          return
    except asyncio.CancelledError:
      raise
    except (ConnectionError, OSError):
      return
    except Exception:
      self._log.exception("unhandled connection error")
    finally:
      await self.close_writer()

  async def close_writer(self) -> None:
    try:
      self._writer.close()
      await self._writer.wait_closed()
    except (ConnectionError, OSError):
      pass

  async def _read_request(self) -> tuple[str, bytes, str, list[tuple[bytes, bytes]]] | None:
    line = b""
    while True:
      line = await self._reader.readline()
      if not line:
        return None
      if line in (b"\r\n", b"\n"):
        continue
      break
    if line[-1:] != b"\n":
      raise _BadRequest("request line too long")
    line = line.rstrip(b"\r\n")
    parts = line.split(b" ")
    if len(parts) != 3:
      raise _BadRequest("malformed request line")
    method_b, target, version_b = parts
    method = method_b.decode("ascii", "replace").upper()
    version = version_b.decode("ascii", "replace")
    if version == "HTTP/1.1":
      hv = "1.1"
    elif version == "HTTP/1.0":
      hv = "1.0"
    else:
      raise _BadVersion(version)
    headers = await _read_headers(self._reader, self._config.request_header_limit)
    return method, target, hv, headers

  async def _handle_http(self, method: str, target: bytes, hv: str, headers: list[tuple[bytes, bytes]]) -> bool:
    raw_path, query = _split_target(target)
    path = _decode_path(raw_path)
    te = _get_header(headers, b"transfer-encoding")
    chunked = te is not None and b"chunked" in te.lower()
    cl = _get_header(headers, b"content-length")
    content_length: int | None = None
    if not chunked and cl is not None:
      try:
        content_length = int(cl)
      except ValueError:
        await _write_error_response(self._writer, hv, 400, "bad content-length")
        return False
      if content_length < 0 or content_length > self._config.max_request_size:
        await _write_error_response(self._writer, hv, 400, "invalid content-length")
        return False
    conn_header = _get_header(headers, b"connection")
    conn_tokens: set[bytes] = set() if conn_header is None else {t.strip().lower() for t in conn_header.split(b",")}
    force_close = (hv == "1.0" and b"keep-alive" not in conn_tokens) or (hv == "1.1" and b"close" in conn_tokens)
    scheme = "https" if self._ssl else "http"
    scope: ASGIScope = {
      "type": "http", "asgi": {"version": "3.0", "spec_version": "2.5"}, "http_version": hv, "method": method, "scheme": scheme,
      "path": path, "raw_path": raw_path, "query_string": query, "root_path": "", "headers": headers, "client": self._client,
      "server": self._server_addr, "extensions": {"http.response.trailers": {}},
    }
    state = self._get_lifespan_state()
    if state is not None:
      scope["state"] = dict(state)
    ctx = _HttpContext(self._reader, self._writer, hv, content_length, chunked, force_close, self._config)
    expect = _get_header(headers, b"expect")
    if expect is not None and b"100-continue" in expect.lower() and hv == "1.1":
      self._writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
      await self._writer.drain()
    app_error: BaseException | None = None
    try:
      await self._app(scope, ctx.receive, ctx.send)
    except asyncio.CancelledError:
      raise
    except _BadRequest as e:
      if not ctx.response_head_sent:
        await ctx.send_error_response(400, str(e))
      return False
    except Exception as e:
      app_error = e
      if not isinstance(e, (ConnectionError, OSError)):
        self._log.debug("http app error", exc_info=True)
    if not ctx.response_head_sent:
      await ctx.send_error_response(500, "Internal Server Error")
    elif not ctx.response_complete:
      ctx.close_after = True
    keep = ctx.response_complete and not ctx.close_after
    if keep:
      try:
        await ctx.drain_body()
      except (ConnectionError, OSError, asyncio.IncompleteReadError):
        keep = False
    if isinstance(app_error, (ConnectionError, OSError)):
      keep = False
    return keep

  async def _handle_ws(self, method: str, target: bytes, headers: list[tuple[bytes, bytes]]) -> None:
    hv = "1.1"
    key = _get_header(headers, b"sec-websocket-key")
    version_h = _get_header(headers, b"sec-websocket-version")
    if method != "GET" or key is None or version_h is None or b"13" not in [t.strip() for t in version_h.split(b",")]:
      await _write_error_response(self._writer, hv, 400, "bad websocket handshake")
      return
    raw_path, query = _split_target(target)
    path = _decode_path(raw_path)
    subprotocols: list[str] = []
    for v in _get_headers_all(headers, b"sec-websocket-protocol"):
      for p in v.split(b","):
        p = p.strip()
        if p:
          subprotocols.append(p.decode("ascii", "replace"))
    scheme = "wss" if self._ssl else "ws"
    extensions: dict[str, dict[str, object]] = {}
    if "websocket.http.response" in self._config.extensions:
      extensions["websocket.http.response"] = {}
    scope: ASGIScope = {
      "type": "websocket", "asgi": {"version": "3.0", "spec_version": "2.5"}, "http_version": "1.1", "scheme": scheme,
      "path": path, "raw_path": raw_path, "query_string": query, "root_path": "", "headers": headers, "client": self._client,
      "server": self._server_addr, "subprotocols": subprotocols, "extensions": extensions,
    }
    state = self._get_lifespan_state()
    if state is not None:
      scope["state"] = dict(state)
    ws = _WsContext(self._reader, self._writer, self._config, _ws_accept_key(key))
    try:
      await self._app(scope, ws.receive, ws.send)
    except asyncio.CancelledError:
      raise
    except Exception:
      self._log.debug("websocket app error", exc_info=True)
    finally:
      await ws.finalize()

class HTTPServer:
  def __init__(self, app: ASGIHandler, config: ServerConfig | None = None) -> None:
    self._app: ASGIHandler = app
    self._config: ServerConfig = config or ServerConfig()
    self._log: logging.Logger = logging.getLogger("rxxxt.httpserver")
    self._log.setLevel(_LOG_LEVELS.get(self._config.log_level.lower(), logging.INFO))
    self._server: asyncio.Server | None = None
    self._conns: set[_Connection] = set()
    self._conn_tasks: set[asyncio.Task[None]] = set()
    self._shutdown_event: asyncio.Event = asyncio.Event()
    self._lifespan_state: dict[str, object] | None = None
    self._lifespan_task: asyncio.Task[None] | None = None
    self._lp_recv: asyncio.Queue[ASGIScope] | None = None
    self._lp_send: asyncio.Queue[Mapping[str, object]] | None = None
    self._abort: bool = False

  async def run(self) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
      try:
        loop.add_signal_handler(sig, self._shutdown_event.set)
      except (NotImplementedError, RuntimeError, ValueError):
        pass
    try:
      await self._lifespan_startup()
      if self._abort:
        return
      self._server = await asyncio.start_server(self._on_conn, self._config.host, self._config.port, ssl=self._config.ssl_context)
      self._log.info("Listening on http%s://%s:%d", "s" if self._config.ssl_context is not None else "", self._config.host, self._config.port)
      _ = await self._shutdown_event.wait()
    except asyncio.CancelledError:
      pass
    finally:
      await self._shutdown()

  async def shutdown(self) -> None:
    self._shutdown_event.set()

  @property
  def port(self) -> int:
    return self._config.port

  async def _on_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    task = asyncio.current_task()
    if task is not None:
      self._conn_tasks.add(task)
    conn = _Connection(self._app, self._config, self._log, reader, writer, lambda: self._lifespan_state)
    self._conns.add(conn)
    try:
      await conn.run()
    except asyncio.CancelledError:
      raise
    except (ConnectionError, OSError):
      pass
    except Exception:
      self._log.exception("connection handler error")
    finally:
      self._conns.discard(conn)
      if task is not None:
        self._conn_tasks.discard(task)
      try:
        writer.close()
        await writer.wait_closed()
      except (ConnectionError, OSError):
        pass

  async def _lifespan_startup(self) -> None:
    state: dict[str, object] = {}
    self._lifespan_state = state
    recv_q: asyncio.Queue[ASGIScope] = asyncio.Queue()
    send_q: asyncio.Queue[Mapping[str, object]] = asyncio.Queue()
    self._lp_recv = recv_q
    self._lp_send = send_q
    scope: ASGIScope = {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}, "state": state}

    async def receive() -> ASGIScope:
      return await recv_q.get()

    async def send(event: Mapping[str, object]) -> None:
      t = _ev_str(event, "type")
      if t not in ("lifespan.startup.complete", "lifespan.startup.failed", "lifespan.shutdown.complete", "lifespan.shutdown.failed"):
        raise ValueError(f"unknown lifespan send event: {t}")
      await send_q.put(event)

    recv_q.put_nowait({"type": "lifespan.startup"})

    async def _run_app() -> None:
      await self._app(scope, receive, send)

    task = asyncio.create_task(_run_app())
    self._lifespan_task = task
    send_wait = asyncio.create_task(send_q.get())
    done, _ = await asyncio.wait({task, send_wait}, timeout=self._config.lifespan_timeout, return_when=asyncio.FIRST_COMPLETED)
    if send_wait in done:
      msg = send_wait.result()
      t = _ev_str(msg, "type")
      if t == "lifespan.startup.complete":
        self._log.debug("lifespan startup complete")
      elif t == "lifespan.startup.failed":
        self._log.error("lifespan startup failed: %s", _ev_opt_str(msg, "message") or "")
        self._abort = True
        _ = task.cancel()
        try:
          await task
        except Exception:
          pass
        self._lifespan_task = None
        self._lifespan_state = None
      else:
        self._log.warning("unexpected lifespan event during startup: %s", t)
      _ = send_wait.cancel()
    elif task in done:
      if not task.cancelled():
        exc = task.exception()
        self._log.debug("lifespan task ended without support: %r", exc)
      self._lifespan_state = None
      self._lifespan_task = None
      _ = send_wait.cancel()
    else:
      self._log.warning("lifespan startup timed out; continuing without lifespan")
      self._lifespan_state = None
      _ = send_wait.cancel()
      if not task.done():
        _ = task.cancel()
        try:
          await task
        except Exception:
          pass
      self._lifespan_task = None

  async def _lifespan_shutdown(self) -> None:
    task = self._lifespan_task
    recv_q = self._lp_recv
    send_q = self._lp_send
    if task is None or task.done() or recv_q is None or send_q is None:
      return
    recv_q.put_nowait({"type": "lifespan.shutdown"})
    send_wait = asyncio.create_task(send_q.get())
    done, _ = await asyncio.wait({task, send_wait}, timeout=self._config.lifespan_timeout, return_when=asyncio.FIRST_COMPLETED)
    if send_wait in done:
      msg = send_wait.result()
      t = _ev_str(msg, "type")
      if t == "lifespan.shutdown.failed":
        self._log.error("lifespan shutdown failed: %s", _ev_opt_str(msg, "message") or "")
      else:
        self._log.debug("lifespan shutdown complete")
    else:
      self._log.warning("lifespan shutdown timed out")
    _ = send_wait.cancel()
    if not task.done():
      _ = task.cancel()
      try:
        await task
      except Exception:
        pass

  async def _shutdown(self) -> None:
    if self._server is not None:
      self._server.close()
      try:
        await self._server.wait_closed()
      except Exception:
        pass
    for conn in list(self._conns):
      try:
        await conn.close_writer()
      except (ConnectionError, OSError):
        pass
    if self._conn_tasks:
      try:
        _ = await asyncio.wait_for(asyncio.gather(*self._conn_tasks, return_exceptions=True), timeout=2)
      except asyncio.TimeoutError:
        for t in self._conn_tasks:
          _ = t.cancel()
        _ = await asyncio.gather(*self._conn_tasks, return_exceptions=True)
    await self._lifespan_shutdown()
