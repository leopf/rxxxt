import unittest
from rxxxt.elements import El
from rxxxt.router import Router
from tests.helpers import element_to_node, render_node

class TestRouter(unittest.IsolatedAsyncioTestCase):
  async def test_basic(self):
    router = Router()
    router.add_route("/hello", lambda: El.div(content=["hello"]))
    router.add_route("/world", lambda: El.div(content=["world"]))

    comp = router()
    node = element_to_node(comp)
    node.context.state.update_state_strs({ "!location": "/hello" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>hello</div>")

    node.context.state.update_state_strs({ "!location": "/world" })
    await node.update()
    self.assertEqual(render_node(node), "<div>world</div>")

    node.context.state.update_state_strs({ "!location": "/no" })
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
    node.context.state.update_state_strs({ "!location": "/hello" })
    await node.expand()
    self.assertEqual(render_node(node), "<div>not found</div>")

    node.context.state.update_state_strs({ "!location": "/var/1" })
    await node.update()
    self.assertEqual(render_node(node), "<div>var1</div>")

    node.context.state.update_state_strs({ "!location": "/var/1/2" })
    await node.update()
    self.assertEqual(render_node(node), "<div>var2</div>")

    await node.destroy()

if __name__ == "__main__":
  _ = unittest.main()
