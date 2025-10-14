import unittest
from rxxxt.elements import El
from rxxxt.helpers import match_path
from rxxxt.router import Router
from tests.helpers import element_to_node, render_node

class TestMatcher(unittest.TestCase):
  def test_basic(self):
    pattern ="/hello/{one}/{all*}"
    self.assertDictEqual(match_path(pattern, "/hello/world/1337/42") or {}, { "one": "world", "all": "1337/42" })
    self.assertDictEqual(match_path(pattern, "/hello/world/1337") or {}, { "one": "world", "all": "1337" })
    self.assertIsNone(match_path(pattern, "/hello/1337"))

  def test_unnamed(self):
    self.assertEqual(match_path("/{*}", "/hello/world/1337"), {})
    self.assertEqual(match_path("/{*}/{one}", "/hello/world/1337"), { "one": "1337" })
    self.assertIsNone(match_path("/{}/{one}", "/hello/world/1337"))
    self.assertEqual(match_path("/{}/{}/{one}", "/hello/world/1337"), { "one": "1337" })
    self.assertEqual(match_path("/{}/{path*}", "/hello/world/1337"), { "path": "world/1337" })

class TestRouter(unittest.IsolatedAsyncioTestCase):
  async def test_basic(self):
    router = Router()
    router.add_route("/hello", lambda: El.div(content=["hello"]))
    router.add_route("/world", lambda: El.div(content=["world"]))

    comp = router()
    node = element_to_node(comp)
    node.context.state.set_many({ "!location": "/hello" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>hello</div>")

    node.context.state.set_many({ "!location": "/world" })
    await node.update()
    self.assertEqual(render_node(node), "<div>world</div>")

    node.context.state.set_many({ "!location": "/no" })
    await node.update()
    self.assertEqual(render_node(node), "<h1>Not found!</h1>")

    await node.destroy()

  async def test_var_path(self):
    router = Router()
    router.add_route("/var/{value}", lambda: El.div(content=["var1"]))
    router.add_route("/var/{a}/{b}", lambda: El.div(content=["var2"]))

    @router.route("/{path*}")
    def _(): return El.div(content=["not found"])

    comp = router()
    node = element_to_node(comp)
    node.context.state.set_many({ "!location": "/hello" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>not found</div>")

    node.context.state.set_many({ "!location": "/var/1" })
    await node.update()
    self.assertEqual(render_node(node), "<div>var1</div>")

    node.context.state.set_many({ "!location": "/var/1/2" })
    await node.update()
    self.assertEqual(render_node(node), "<div>var2</div>")

    await node.destroy()

if __name__ == "__main__":
  _ = unittest.main()
