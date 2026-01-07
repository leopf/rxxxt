import importlib.resources, os, unittest, httpx, httpx_ws, httpx_ws.transport
from typing import Annotated
from rxxxt.app import App, AppHttpRequest, AppWebsocketInitMessage, AppWebsocketUpdateMessage
from rxxxt.asgi import ASGIHandler
from rxxxt.component import Component, event_handler, local_state
from rxxxt.elements import El, Element, lazy_element
from rxxxt.execution import Context, InputEvent
from rxxxt.state import default_state_resolver
from tests.helpers import TrackedCustomAttribute

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

  async def test_initial_expand(self):
    @lazy_element
    def header_test(context: Context):
      return El.div(content=[";".join(context.get_header("x-test"))])

    app = App(header_test)
    async with self._get_client(app) as client:
      r = await client.get("/", headers={ "x-test": "hello world" })
      self.assertIn("hello world", r.text)

  @unittest.skipIf(int(os.getenv("CI", "0")), "skipped in CI, build not present there.")
  async def test_frontend_script(self):
    app = App(lambda: El.div())
    async with self._get_client(app) as client:
      r = await client.get("/rxxxt-client.js")
      ref_text = importlib.resources.read_text("rxxxt.assets", "main.js")
      self.assertEqual(r.text, ref_text)

  async def test_ws(self):
    add_tracked = TrackedCustomAttribute()

    class Adder(Component):
      counter = local_state(int)

      @event_handler()
      def add(self, value: Annotated[int, "target.value"]):
        self.counter += value

      def render(self):
        return El.div(onclick=add_tracked(self.add), content=[f"c{self.counter}"])

    state_resolver = default_state_resolver()
    app = App(Adder, state_resolver)
    client = self._get_client(app, True)
    _ = await client.get("/")
    token = state_resolver.create_token({}, None)
    async with httpx_ws.aconnect_ws(str(client.base_url), client) as ws:
      await ws.send_text(AppWebsocketInitMessage(type="init", state_token=token, enable_state_updates=False).model_dump_json())
      await add_tracked.set_event.wait()
      await ws.send_text(AppWebsocketUpdateMessage(type="update", events=(
        InputEvent(context_id=add_tracked.last_context.sid, data={ "value": 5 }),), location="/").model_dump_json())
      response_text = await ws.receive_text()
      self.assertIn("c5", response_text)


if __name__ == "__main__":
  _ = unittest.main()
