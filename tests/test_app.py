import importlib.resources
import os
from typing import Annotated
import unittest
from rxxxt.app import App, AppHttpRequest, AppWebsocketInitMessage, AppWebsocketUpdateMessage
from rxxxt.asgi import ASGIHandler
from rxxxt.component import Component, event_handler
from rxxxt.elements import El, Element
import httpx
import httpx_ws
import httpx_ws.transport

from rxxxt.events import ContextInputEvent
from rxxxt.state import default_state_resolver, local_state

class TestApp(unittest.IsolatedAsyncioTestCase):

  def _get_client(self, app: ASGIHandler, websocket: bool = False):
    if websocket: transport = httpx_ws.transport.ASGIWebSocketTransport(app)
    else: transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")

  async def test_value_error(self):
    def el_fac() -> Element:
      raise ValueError("Testing...")

    app = App(el_fac)
    async with self._get_client(app) as client:
      r = await client.get("/")
      self.assertEqual(r.status_code, 400)

  async def test_generic_error(self):
    def el_fac() -> Element:
      raise Exception("Testing...")

    app = App(el_fac)
    async with self._get_client(app) as client:
      r = await client.get("/")
      self.assertEqual(r.status_code, 500)

  async def test_not_found_error(self):
    app = App(lambda: El.div())
    async with self._get_client(app) as client:
      r = await client.put("/")
      self.assertEqual(r.status_code, 404)

  async def test_post(self):
    state_resolver = default_state_resolver()
    app = App(lambda: El.div(), state_resolver)
    async with self._get_client(app) as client:
      token = state_resolver.create_token({}, None)
      r = await client.post("/", json=AppHttpRequest(state_token=token, events=()).model_dump())
      self.assertEqual(r.status_code, 200)

  async def test_basic(self):
    text = "This is a test of the app!"
    app = App(lambda: El.div(content=[text]))
    async with self._get_client(app) as client:
      r = await client.get("/")
      self.assertIn(text, r.text)

  @unittest.skipIf(int(os.getenv("CI", "0")), "skipped in CI, build not present there.")
  async def test_frontend_script(self):
    app = App(lambda: El.div())
    async with self._get_client(app) as client:
      r = await client.get("/rxxxt-client.js")
      ref_text = importlib.resources.read_text("rxxxt.assets", "main.js")
      self.assertEqual(r.text, ref_text)

  async def test_ws(self):
    context_id: str = ""
    class Counter(Component):
      counter = local_state(int)

      async def on_init(self) -> None:
        nonlocal context_id
        context_id = self.context.sid

      @event_handler()
      def add(self, value: Annotated[int, "target.value"]):
        self.counter += value

      def render(self):
        return El.div(content=[f"c{self.counter}"])

    state_resolver = default_state_resolver()
    app = App(Counter, state_resolver)
    client = self._get_client(app, True)
    _ = await client.get("/")
    token = state_resolver.create_token({}, None)
    async with httpx_ws.aconnect_ws(str(client.base_url), client) as ws:
      await ws.send_text(AppWebsocketInitMessage(type="init", state_token=token, enable_state_updates=False).model_dump_json())
      await ws.send_text(AppWebsocketUpdateMessage(type="update", events=(
        ContextInputEvent(context_id=context_id, data={ "$handler_name": "add", "value": 5 }),), location="/").model_dump_json())
      response_text = await ws.receive_text()
      self.assertIn("c5", response_text)


if __name__ == "__main__":
  _ = unittest.main()
