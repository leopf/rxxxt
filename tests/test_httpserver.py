import asyncio
import socket as _socket
import ssl
import unittest
from collections.abc import Mapping, MutableMapping
from typing import cast

import httpx
import httpx_ws
from rxxxt.asgi import ASGIFnReceive, ASGIFnSend, ASGIHandler, ASGIScope
from rxxxt.httpserver import HTTPServer, ServerConfig

def _free_port() -> int:
  s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
  try:
    s.bind(("127.0.0.1", 0))
    return cast(int, s.getsockname()[1])
  finally:
    s.close()

def _scope_echo_app() -> ASGIHandler:
  async def app(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
    assert scope["asgi"]["version"] == "3.0"
    stype = cast(str, scope["type"])
    if stype == "lifespan":
      while True:
        m = await receive()
        mt = cast(str, m["type"])
        if mt == "lifespan.startup":
          await send({"type": "lifespan.startup.complete"})
        elif mt == "lifespan.shutdown":
          await send({"type": "lifespan.shutdown.complete"})
          return
    if stype == "http":
      body = b""
      more = True
      while more:
        m = await receive()
        body += cast(bytes, m.get("body", b""))
        more = cast(bool, m.get("more_body", False))
      await send({"type": "http.response.start", "status": 200, "headers": [(b"x-scope-type", cast(str, scope["type"]).encode())]})
      await send({"type": "http.response.body", "body": b"echo:" + body})
    elif stype == "websocket":
      _ = await receive()
      await send({"type": "websocket.accept"})
      while True:
        m = await receive()
        mt = cast(str, m["type"])
        if mt == "websocket.disconnect":
          return
        b = m.get("bytes")
        if b is not None:
          await send({"type": "websocket.send", "bytes": b})
        elif m.get("text") is not None:
          await send({"type": "websocket.send", "text": m["text"]})
  return app

class _ServerRunner:
  _server: HTTPServer
  _task: asyncio.Task[None] | None

  def __init__(self, app: ASGIHandler, config: ServerConfig | None = None) -> None:
    self._server = HTTPServer(app, config)
    self._task = None

  async def __aenter__(self) -> HTTPServer:
    self._task = asyncio.create_task(self._server.run())
    for _ in range(100):
      s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
      try:
        s.settimeout(0.1)
        s.connect(("127.0.0.1", self._server.port))
        break
      except OSError:
        await asyncio.sleep(0.02)
      finally:
        s.close()
    else:
      raise RuntimeError("server did not start")
    return self._server

  async def __aexit__(self, *exc: object) -> None:
    await self._server.shutdown()
    if self._task is not None:
      try:
        await asyncio.wait_for(self._task, timeout=5)
      except asyncio.TimeoutError:
        _ = self._task.cancel()

class TestHTTP(unittest.IsolatedAsyncioTestCase):
  async def test_get_simple(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/hello")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "echo:")
        self.assertEqual(r.headers["x-scope-type"], "http")

  async def test_post_body(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.post(f"http://127.0.0.1:{srv.port}/", content=b"hello world")
        self.assertEqual(r.content, b"echo:hello world")

  async def test_query_and_path_decoding(self) -> None:
    seen: dict[str, object] = {}
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      seen["path"] = scope["path"]
      seen["qs"] = scope["query_string"]
      seen["raw_path"] = scope["raw_path"]
      await send({"type": "http.response.start", "status": 204, "headers": []})
      await send({"type": "http.response.body"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/caf%C3%A9?x=1&y=2")
        self.assertEqual(r.status_code, 204)
      self.assertEqual(seen["path"], "/café")
      self.assertEqual(seen["qs"], b"x=1&y=2")
      self.assertEqual(seen["raw_path"], b"/caf%C3%A9")

  async def test_chunked_request_body(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
      writer.write(b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"echo:hello world", data)

  async def test_streamed_chunked_response(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      await send({"type": "http.response.start", "status": 200, "headers": []})
      for chunk in (b"a", b"b", b"c"):
        await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await asyncio.sleep(0.01)
      await send({"type": "http.response.body", "body": b"", "more_body": False})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"transfer-encoding: chunked", data.lower())
      self.assertIn(b"1\r\na\r\n1\r\nb\r\n1\r\nc\r\n0\r\n\r\n", data)

  async def test_keepalive_reuse(self) -> None:
    async def app(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      out = b"echo:" + cast(str, scope["path"]).encode()
      await send({"type": "http.response.start", "status": 200, "headers": [(b"content-length", str(len(out)).encode())]})
      await send({"type": "http.response.body", "body": out})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      for i in range(3):
        writer.write(f"GET /{i} HTTP/1.1\r\nHost: x\r\nConnection: keep-alive\r\n\r\n".encode())
        await writer.drain()
        status = await reader.readline()
        self.assertIn(b"200", status)
        cl = 0
        while True:
          line = await reader.readline()
          if line in (b"\r\n", b""):
            break
          if line.lower().startswith(b"content-length:"):
            cl = int(line.split(b":")[1].strip())
        body = await reader.readexactly(cl)
        self.assertEqual(body, f"echo:/{i}".encode())
      writer.close()
      await writer.wait_closed()

  async def test_http10_close_delimited(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      await send({"type": "http.response.start", "status": 200, "headers": []})
      await send({"type": "http.response.body", "body": b"hello10"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"GET / HTTP/1.0\r\nHost: x\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"connection: close", data.lower())
      self.assertIn(b"hello10", data)
      self.assertNotIn(b"transfer-encoding", data.lower())

  async def test_app_error_sends_500(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, _send: ASGIFnSend) -> None:
      raise RuntimeError("boom")
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.status_code, 500)

  async def test_app_no_response_sends_500(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, _send: ASGIFnSend) -> None:
      return
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.status_code, 500)

  async def test_bad_request(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"not a request line\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"400", data)

  async def test_404_via_app(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      await send({"type": "http.response.start", "status": 404, "headers": []})
      await send({"type": "http.response.body", "body": b"nope"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/missing")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content, b"nope")

  async def test_client_disconnect_mid_body(self) -> None:
    received: dict[str, Mapping[str, object]] = {}
    async def app(scope: ASGIScope, receive: ASGIFnReceive, _send: ASGIFnSend) -> None:
      if scope["type"] != "http":
        return
      try:
        m = await receive()
        received["first"] = m
      except Exception:
        pass
      await asyncio.sleep(0.2)
      try:
        m = await receive()
        received["second"] = m
      except Exception:
        pass
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      _reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\nConnection: close\r\n\r\nab")
      await writer.drain()
      await asyncio.sleep(0.05)
      writer.close()
      await writer.wait_closed()
      await asyncio.sleep(0.25)
    first = received.get("first", {})
    self.assertEqual(first.get("body"), b"ab")

  async def test_large_post_within_limit(self) -> None:
    payload = b"x" * 100000
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.post(f"http://127.0.0.1:{srv.port}/", content=payload)
        self.assertEqual(r.content, b"echo:" + payload)

  async def test_content_length_over_limit(self) -> None:
    payload = b"x" * 1000
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning", max_request_size=100)) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.post(f"http://127.0.0.1:{srv.port}/", content=payload)
        self.assertEqual(r.status_code, 400)

  async def test_http_505_unsupported_version(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"GET / HTTP/2.0\r\nHost: x\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"505", data)

  async def test_absolute_form_uri(self) -> None:
    seen: dict[str, object] = {}
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      seen["raw_path"] = scope["raw_path"]
      seen["path"] = scope["path"]
      await send({"type": "http.response.start", "status": 204, "headers": []})
      await send({"type": "http.response.body"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"GET http://example.com/abs?q=1 HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
      await writer.drain()
      _ = await reader.read()
      writer.close()
      await writer.wait_closed()
    self.assertEqual(seen["raw_path"], b"/abs")
    self.assertEqual(seen["path"], "/abs")

  async def test_bad_chunk_size(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\nzz\r\nhello\r\n0\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"400", data)

  async def test_response_trailers(self) -> None:
    async def app(_scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      await send({"type": "http.response.start", "status": 200, "headers": [], "trailers": True})
      await send({"type": "http.response.body", "body": b"hi", "more_body": True})
      await send({"type": "http.response.trailers", "headers": [(b"x-trailer", b"done")], "more_trailers": False})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"transfer-encoding: chunked", data.lower())
      self.assertIn(b"x-trailer: done", data)

  async def test_body_before_start_raises(self) -> None:
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      if scope["type"] != "http":
        return
      try:
        await send({"type": "http.response.body", "body": b"x"})
      except ValueError:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"caught"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.text, "caught")

  async def test_unknown_http_send_event(self) -> None:
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      if scope["type"] != "http":
        return
      try:
        await send({"type": "http.bogus"})
      except ValueError:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"caught"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.text, "caught")

  async def test_asterisk_request_target(self) -> None:
    seen: dict[str, object] = {}
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      seen["path"] = scope["path"]
      seen["raw_path"] = scope["raw_path"]
      await send({"type": "http.response.start", "status": 204, "headers": []})
      await send({"type": "http.response.body"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      writer.write(b"OPTIONS * HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
      await writer.drain()
      _ = await reader.read()
      writer.close()
      await writer.wait_closed()
    self.assertEqual(seen["path"], "*")
    self.assertEqual(seen["raw_path"], b"*")

  async def test_unknown_status_reason(self) -> None:
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      if scope["type"] != "http":
        return
      await send({"type": "http.response.start", "status": 999, "headers": []})
      await send({"type": "http.response.body", "body": b"weird"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.status_code, 999)

class TestWebSocket(unittest.IsolatedAsyncioTestCase):
  async def test_handshake_and_echo_text(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c) as ws:
          await ws.send_text("hello")
          self.assertEqual(await ws.receive_text(), "hello")

  async def test_echo_binary(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c) as ws:
          await ws.send_bytes(b"\x00\x01\x02")
          self.assertEqual(await ws.receive_bytes(), b"\x00\x01\x02")

  async def test_subprotocol_negotiation(self) -> None:
    chosen: dict[str, object] = {}
    async def app(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      chosen["subs"] = scope["subprotocols"]
      _ = await receive()
      await send({"type": "websocket.accept", "subprotocol": "proto2"})
      await send({"type": "websocket.close"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c, subprotocols=["proto1", "proto2"]):
          pass
    self.assertEqual(chosen["subs"], ["proto1", "proto2"])

  async def test_app_close_before_accept_returns_403(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.close"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"403", data)

  async def test_ping_pong(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      resp = await reader.readuntil(b"\r\n\r\n")
      self.assertIn(b"101", resp)
      mask = b"\x12\x34\x56\x78"
      payload = b"pingdata"
      masked = bytes(payload[i] ^ mask[i & 3] for i in range(len(payload)))
      frame = bytes([0x89, 0x80 | len(payload)]) + mask + masked
      writer.write(frame)
      await writer.drain()
      pong = await reader.readexactly(2 + len(payload))
      self.assertEqual(pong[0] & 0x0f, 0x0a)
      self.assertEqual(pong[2:], payload)
      writer.close()
      await writer.wait_closed()

  async def test_client_initiated_close(self) -> None:
    disconnect_code: dict[str, object] = {}
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.accept"})
      while True:
        m = await receive()
        if m["type"] == "websocket.disconnect":
          disconnect_code["code"] = m.get("code")
          return
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c) as ws:
          await ws.send_bytes(b"hi")
    self.assertEqual(disconnect_code.get("code"), 1000)

  async def test_message_too_big(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning", ws_max_size=64)) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c) as ws:
          await ws.send_bytes(b"x" * 65)
          with self.assertRaises(httpx_ws.WebSocketDisconnect):
            _ = await ws.receive_bytes()

  async def test_fragmented_text_message(self) -> None:
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      _ = await reader.readuntil(b"\r\n\r\n")
      mask = b"\xaa\xbb\xcc\xdd"
      def mk(opcode: int, payload: bytes, fin: bool) -> bytes:
        masked = bytes(payload[i] ^ mask[i & 3] for i in range(len(payload)))
        b0 = (0x80 if fin else 0) | opcode
        return bytes([b0, 0x80 | len(payload)]) + mask + masked
      writer.write(mk(0x1, b"foo ", fin=False) + mk(0x0, b"bar", fin=True))
      await writer.drain()
      fr = await reader.readexactly(2)
      ln = fr[1] & 0x7f
      payload = await reader.readexactly(ln)
      self.assertEqual(fr[0] & 0x0f, 0x1)
      self.assertEqual(payload, b"foo bar")
      writer.close()
      await writer.wait_closed()

  async def test_ws_http_response_extension(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.http.response.start", "status": 401, "headers": [(b"x-custom", b"yes")]})
      await send({"type": "websocket.http.response.body", "body": b"denied", "more_body": False})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"401", data)
      self.assertIn(b"x-custom: yes", data)
      self.assertIn(b"denied", data)

  async def test_send_before_accept_raises(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      try:
        await send({"type": "websocket.send", "text": "x"})
      except ValueError:
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.send", "text": "recovered"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c) as ws:
          self.assertEqual(await ws.receive_text(), "recovered")

  async def test_unmasked_client_frame_rejected(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.accept"})
      m = await receive()
      if m["type"] != "websocket.disconnect":
        await send({"type": "websocket.close"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      _ = await reader.readuntil(b"\r\n\r\n")
      writer.write(bytes([0x81, 0x05]) + b"hello")
      await writer.drain()
      _ = await reader.read()
      writer.close()
      await writer.wait_closed()

  async def test_continuation_without_fragment(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.accept"})
      m = await receive()
      if m["type"] != "websocket.disconnect":
        await send({"type": "websocket.close"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      _ = await reader.readuntil(b"\r\n\r\n")
      mask = b"\x01\x02\x03\x04"
      payload = b"x"
      masked = bytes(payload[i] ^ mask[i & 3] for i in range(len(payload)))
      writer.write(bytes([0x80, 0x80 | 1]) + mask + masked)
      await writer.drain()
      _ = await reader.read()
      writer.close()
      await writer.wait_closed()

  async def test_ws_disconnect_code_1005_on_eof(self) -> None:
    seen: dict[str, object] = {}
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.accept"})
      m = await receive()
      seen["code"] = m.get("code")
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      _ = await reader.readuntil(b"\r\n\r\n")
      writer.close()
      await writer.wait_closed()
      await asyncio.sleep(0.1)
    self.assertEqual(seen.get("code"), 1005)

  async def test_ws_app_accepts_but_does_not_close(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      _ = await receive()
      await send({"type": "websocket.accept"})
      await asyncio.sleep(0.3)
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      async with httpx.AsyncClient() as c:
        async with httpx_ws.aconnect_ws(f"http://127.0.0.1:{srv.port}/", c):
          await asyncio.sleep(0.1)

  async def test_ws_app_neither_accepts_nor_closes(self) -> None:
    async def app(_scope: ASGIScope, receive: ASGIFnReceive, _send: ASGIFnSend) -> None:
      _ = await receive()
      await asyncio.sleep(0.3)
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="error")) as srv:
      reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
      key = b"dGhlIHNhbXBsZSBub25jZQ=="
      writer.write(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
                   b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
      await writer.drain()
      data = await reader.read()
      writer.close()
      await writer.wait_closed()
      self.assertIn(b"403", data)

class TestLifespan(unittest.IsolatedAsyncioTestCase):
  async def test_lifespan_complete_and_state(self) -> None:
    state_seen: dict[str, object] = {}
    async def app(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      stype = cast(str, scope["type"])
      if stype == "lifespan":
        while True:
          m = await receive()
          mt = cast(str, m["type"])
          if mt == "lifespan.startup":
            scope["state"]["db"] = "connected"
            await send({"type": "lifespan.startup.complete"})
          elif mt == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return
      elif stype == "http":
        state = cast("MutableMapping[str, object]", scope["state"])
        state_seen["db"] = state.get("db")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning")) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.status_code, 200)
    self.assertEqual(state_seen["db"], "connected")

  async def test_no_lifespan_support(self) -> None:
    async def app(scope: ASGIScope, _receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      if scope["type"] != "lifespan":
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    async with _ServerRunner(app, ServerConfig(port=_free_port(), log_level="warning", lifespan_timeout=1.0)) as srv:
      async with httpx.AsyncClient() as c:
        r = await c.get(f"http://127.0.0.1:{srv.port}/")
        self.assertEqual(r.status_code, 200)

  async def test_lifespan_startup_failed_aborts(self) -> None:
    async def app(scope: ASGIScope, receive: ASGIFnReceive, send: ASGIFnSend) -> None:
      if scope["type"] == "lifespan":
        _ = await receive()
        await send({"type": "lifespan.startup.failed", "message": "nope"})
    srv = HTTPServer(app, ServerConfig(port=_free_port(), log_level="warning", lifespan_timeout=1.0))
    task = asyncio.create_task(srv.run())
    await asyncio.sleep(0.3)
    try:
      async with httpx.AsyncClient() as c:
        with self.assertRaises((httpx.ConnectError, OSError)):
          _ = await c.get(f"http://127.0.0.1:{srv.port}/", timeout=0.5)
    finally:
      await srv.shutdown()
      try:
        await asyncio.wait_for(task, timeout=2)
      except asyncio.TimeoutError:
        _ = task.cancel()

class TestTLS(unittest.IsolatedAsyncioTestCase):
  async def test_https_and_wss(self) -> None:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile="tests/cert.pem", keyfile="tests/key.pem")
    async with _ServerRunner(_scope_echo_app(), ServerConfig(port=_free_port(), log_level="warning", ssl_context=ctx)) as srv:
      client_ctx = ssl.create_default_context()
      client_ctx.check_hostname = False
      client_ctx.verify_mode = ssl.CERT_NONE
      async with httpx.AsyncClient(verify=client_ctx) as c:
        r = await c.get(f"https://127.0.0.1:{srv.port}/secure")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, "echo:")

if __name__ == "__main__":
  _ = unittest.main()
