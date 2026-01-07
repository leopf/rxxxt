from collections import defaultdict
import unittest, typing
from rxxxt.elements import El, lazy_element
from rxxxt.component import Component, event_handler, local_state, local_state_box
from rxxxt.execution import Context, InputEvent
from rxxxt.page import default_page
from rxxxt.session import AppConfig, Session, SessionConfig
from rxxxt.state import JWTStateResolver
from tests.helpers import TrackedCustomAttribute

session_config = SessionConfig(page_facotry=default_page, state_resolver=JWTStateResolver(b"deez"), persistent=False, app_config=AppConfig())

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

  async def test_cookie_parsing(self):
    @lazy_element
    def main(context: Context):
      return El.div(content=[ context.cookies.get("hello", ""), context.cookies.get("world", "") ])

    async with Session(session_config, main()) as session:
      session.set_location("/")
      session.set_headers({ "cookie": (" hello=world; world=hello",) })
      await session.init(None)

      update = await session.render_update(True, True)
      self.assertIn("worldhello", update.html_parts[0])

  async def test_output_event_refresh(self):
    class Main(Component):
      def render(self):
        return El.div(content=[])

    el = Main()
    async with Session(session_config, el) as session:
      await session.init(None)
      _update1 = await session.render_update(True, True)
      self.assertFalse(session.update_pending)
      el.context.emit("download", { "url": "https://google.com" })
      self.assertTrue(session.update_pending)
      update2 = await session.render_update(True, False)
      self.assertEqual(len(update2.html_parts), 0)
      self.assertEqual(len(update2.events), 1)
      self.assertEqual(update2.events[0], dict(event="custom", name="download", data={ "url": "https://google.com" }))

  async def test_partial_update(self):
    class Inner(Component):
      value = local_state(str)

      async def on_init(self) -> None:
        self.value = "1337"

      def render(self): return El.div(content=[self.value])

    class Outer(Component):
      def __init__(self) -> None:
        super().__init__()
        self.inner = Inner()

      def render(self): return El.div(content=[
        "hello",
        self.inner,
        "world"
      ])

    outer = Outer()
    async with Session(session_config, outer) as session:
      session.set_location("/")
      await session.init(None)
      await session.update()
      update1 = await session.render_update(True, True)
      self.assertIn("hello", update1.html_parts[0])
      self.assertIn("world", update1.html_parts[0])
      self.assertIn("1337", update1.html_parts[0])

      outer.inner.value = "133742"
      self.assertIn(outer.inner.context.id, session.execution.pending_updates)
      self.assertEqual(len(session.execution.pending_updates), 1)
      await session.update()

      update2 = await session.render_update(True, False)
      self.assertEqual(len(update2.html_parts), 1)
      self.assertNotIn("hello", update2.html_parts[0])
      self.assertNotIn("world", update2.html_parts[0])
      self.assertIn("133742", update2.html_parts[0])

    outer = Outer()
    async with Session(session_config, outer) as session:
      session.set_location("/")
      await session.init(update2.state_token)
      outer.inner.value = "247331"
      self.assertIn(outer.inner.context.id, session.execution.pending_updates)
      self.assertEqual(len(session.execution.pending_updates), 1)
      await session.update()

      update3 = await session.render_update(True, False)
      self.assertEqual(len(update3.html_parts), 1)
      self.assertNotIn("hello", update3.html_parts[0])
      self.assertNotIn("world", update3.html_parts[0])
      self.assertIn("247331", update3.html_parts[0])

  async def test_input_event_handling_order(self):
    event_outputs: list[str] = []
    inner_tracked = TrackedCustomAttribute()
    outer_tracked = TrackedCustomAttribute()

    class Inner(Component):
      @event_handler()
      def on_event(self, value: str): event_outputs.append(value)
      def render(self): return El.div(onclick=inner_tracked(self.on_event))

    class Outer(Component):
      @event_handler()
      def on_event(self, value: str): event_outputs.append(value)
      def render(self): return El.div(onclick=outer_tracked(self.on_event), content=[Inner()])

    outer = Outer()
    async with Session(session_config, outer) as session:
      session.set_location("/")
      await session.init(None)
      assert inner_tracked.last_context is not None
      assert outer_tracked.last_context is not None
      await session.handle_events((
        InputEvent(context_id=inner_tracked.last_context.sid, data={ "value": "a" }),
        InputEvent(context_id=outer_tracked.last_context.sid, data={ "value": "b" }),
      ))
      await session.update()
      self.assertEqual(event_outputs, ["a", "b"])

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
        dict(event="navigate", location = "/hello-world"),
        dict(event="navigate", location = "/world-hello")
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
        self.context.request_update()
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
