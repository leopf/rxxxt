import unittest

from rxxxt.elements import El
from rxxxt.component import Component
from rxxxt.events import NavigateOutputEvent
from rxxxt.page import default_page
from rxxxt.session import Session, SessionConfig
from rxxxt.state import JWTStateResolver

session_config = SessionConfig(page_facotry=default_page, state_resolver=JWTStateResolver(b"deez"), persistent=False)

class TestSession(unittest.IsolatedAsyncioTestCase):
  async def test_state_cell_update(self):
    class Main(Component):
      def render(self):
        return El.div(content=[self.context.path])

    async with Session(session_config, Main()) as session:
      session.set_location("/hello-world")
      await session.init(None)
      update1 = await session.render_update(True, True)
      self.assertIn("/hello-world", update1.html_parts[0])

    async with Session(session_config, Main()) as session:
      await session.init(update1.state_token)
      session.set_location("/world-hello")
      await session.handle_events(()) # this should not matter but we want to match the App flow
      await session.update()
      update2 = await session.render_update(True, True)
      self.assertIn("/world-hello", update2.html_parts[0])

  async def test_event_deduplication(self):
    class Main(Component):
      def render(self):
        self.context.navigate("/hello-world")
        self.context.navigate("/world-hello")
        self.context.navigate("/hello-world")
        return El.div()

    async with Session(session_config, Main()) as session:
      session.set_location("/")
      await session.init(None)
      update = await session.render_update(True, True)
      self.assertEqual(update.events, (
        NavigateOutputEvent(location = "/hello-world"),
        NavigateOutputEvent(location = "/world-hello")
      ))

if __name__ == "__main__":
  _ = unittest.main()
