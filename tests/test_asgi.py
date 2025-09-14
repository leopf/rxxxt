import unittest, httpx, httpx_ws, httpx_ws.transport
from rxxxt.asgi import ASGIHandler, Composer, WebsocketContext, websocket_handler

class TestASGI(unittest.IsolatedAsyncioTestCase):
  def _get_client(self, app: ASGIHandler, websocket: bool = False):
    if websocket: transport = httpx_ws.transport.ASGIWebSocketTransport(app)
    else: transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")

  async def test_ws_error(self):
    composer = Composer()
    @composer.add_handler
    @websocket_handler
    async def _(context: WebsocketContext):
      if context.path != "/hello-world": context.next()
      await context.setup()
      raise RuntimeError()

    @composer.add_handler
    def _(*_): raise RuntimeError()

    client = self._get_client(composer, True)
    with self.assertRaises(httpx_ws.WebSocketDisconnect) as outer_error:
      async with httpx_ws.aconnect_ws(str(client.base_url) + "/world-hello", client): pass

    self.assertEqual(outer_error.exception.code, 1011)

    with self.assertRaises(httpx_ws.WebSocketDisconnect) as inner_error:
      async with httpx_ws.aconnect_ws(str(client.base_url) + "/hello-world", client) as ws:
        _r = await ws.receive_bytes(0.1)

    self.assertEqual(inner_error.exception.code, 1011)

  async def test_ws_messages(self):
    composer = Composer()
    @composer.add_handler
    @websocket_handler
    async def _(context: WebsocketContext):
      await context.setup()
      await context.send_message(b"hello")

    client = self._get_client(composer, True)
    async with httpx_ws.aconnect_ws(str(client.base_url) + "/", client) as ws:
      self.assertEqual(await ws.receive_bytes(), b"hello")
      await ws.close()

  async def test_composer_http_error_400(self):
    composer = Composer()
    @composer.add_handler
    def _(*_): raise ValueError()

    async with self._get_client(composer) as client:
      response = await client.get("/hello-world")
      self.assertEqual(response.status_code, 400)

  async def test_composer_http_error_500(self):
    composer = Composer()
    @composer.add_handler
    def _(*_): raise RuntimeError()

    async with self._get_client(composer) as client:
      response = await client.get("/hello-world")
      self.assertEqual(response.status_code, 500)

if __name__ == "__main__":
  _ = unittest.main()
