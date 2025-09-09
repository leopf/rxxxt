import unittest

from rxxxt.elements import El
from rxxxt.component import Component
from rxxxt.page import default_page
from rxxxt.session import Session, SessionConfig
from rxxxt.state import JWTStateResolver

class TestSession(unittest.IsolatedAsyncioTestCase):
  @unittest.skip("working on this fix")
  async def test_state_cell_update(self):
    config = SessionConfig(page_facotry=default_page, state_resolver=JWTStateResolver(b"deez"), persistent=False)

    class Main(Component):
      def render(self):
        return El.div(content=[self.context.path])

    async with Session(config, Main()) as session:
      session.set_location("/hello-world")
      await session.init(None)
      update1 = await session.render_update(True, True)
      self.assertIn("/hello-world", update1.html_parts[0])

    async with Session(config, Main()) as session:
      await session.init(update1.state_token)
      session.set_location("/world-hello")
      await session.handle_events(()) # this should not matter but we want to match the App flow
      await session.update()
      update2 = await session.render_update(True, True)
      self.assertIn("/world-hello", update2.html_parts[0])

if __name__ == "__main__":
  _ = unittest.main()
