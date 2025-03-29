import unittest
from rxxxt.app import App
from rxxxt.asgi import ASGIHandler
from rxxxt.elements import El
import httpx

class TestApp(unittest.IsolatedAsyncioTestCase):

  def _get_client(self, app: ASGIHandler):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")

  async def test_basic(self):
    text = "This is a test of the app!"
    app = App(lambda: El.div(content=[text]))
    async with self._get_client(app) as client:
      r = await client.get("/")
      self.assertIn(text, r.text)

if __name__ == "__main__":
  unittest.main()
