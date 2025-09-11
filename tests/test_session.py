from collections import defaultdict
import unittest, typing
from rxxxt.elements import El
from rxxxt.component import Component
from rxxxt.events import NavigateOutputEvent
from rxxxt.page import default_page
from rxxxt.session import Session, SessionConfig
from rxxxt.state import JWTStateResolver, local_state, local_state_box

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

  async def test_deep_state_update(self):
    class Main(Component):
      data = local_state_box(dict[str, typing.Any])
      async def on_init(self) -> None:
        self.data.value = { "hello": "no" }
      def render(self):
        return El.div(content=[ self.data.value.get("hello", "") ])

    el = Main()
    async with Session(session_config, el) as session:
      session.set_location("/")
      await session.init(None)
      el.data.value["hello"] = "yes"
      el.data.update()
      if session.update_pending:
        await session.update()
      update = await session.render_update(True, True)
      self.assertIn("yes", update.html_parts[0])

  async def test_lifecycle(self):
    testobj = self
    counters: defaultdict[str, int] = defaultdict(int)
    class Main(Component):
      async def on_init(self) -> None:
        testobj.assertEqual(counters["before_destroy"], 0)
        counters["init"] += 1
      async def on_before_update(self) -> None:
        testobj.assertEqual(counters["render"], counters["before_update"])
        counters["before_update"] += 1
      def render(self):
        self.context.request_update()
        counters["render"] += 1
        testobj.assertEqual(counters["render"], counters["before_update"])
        return El.div()
      async def on_after_update(self) -> None:
        counters["after_update"] += 1
        testobj.assertEqual(counters["after_update"], counters["render"])
      async def on_before_destroy(self) -> None:
        testobj.assertEqual(counters["init"], 1)
        testobj.assertEqual(counters["before_destroy"], 0)
        counters["before_destroy"] += 1
      async def on_after_destroy(self) -> None:
        counters["after_destroy"] += 1
        testobj.assertEqual(counters["after_destroy"], counters["before_destroy"])

    class Switcher(Component):
      hidden = local_state(bool)
      def render(self):
        if self.hidden: return El.div()
        else: return Main()

    el = Switcher()
    async with Session(session_config, el) as session:
      session.set_location("/")
      await session.init(None)
      await session.update()
      self.assertEqual(counters["render"], 2)
      self.assertEqual(counters["after_destroy"], 0)
      el.hidden = True
      await session.update()
      self.assertEqual(counters["after_destroy"], 1)

if __name__ == "__main__":
  _ = unittest.main()
