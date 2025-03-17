from ast import Try
import asyncio
import uvicorn
from rxxxt import Component, event_handler, El, Element, App, Router
import logging

from rxxxt.component import HandleNavigate

logging.basicConfig(level=logging.DEBUG)

class Counter(Component):
  @property
  def state_id(self): return f"{self.context.sid}count"

  @property
  def count(self): return int(self.context.get_state(self.state_id) or "0")

  @event_handler()
  def increment(self):
    self.context.set_state(self.state_id, str(self.count + 1))

  async def on_init(self) -> None:
    self.add_background_task(self.auto_incrementer())

  async def auto_incrementer(self):
    while True:
      await asyncio.sleep(2)
      self.increment()

  def render(self) -> Element:
    return El.div(onclick=self.increment, content=[f"Count: {self.count}"])

class Outer(Component):

  async def on_init(self) -> None:
    if not self.context.config.persistent: self.context.use_websocket()

  @event_handler()
  def nav2_hdl(self): self.context.navigate("/?nav2")

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[f"QS: {self.context.query_string}"]),
      El.div(content=["nav 1"], onclick=HandleNavigate("/?nav1")),
      El.div(content=["nav 2"], onclick=self.nav2_hdl),
      El.div(content=["Counter 1:"]),
      Counter(),
      El.div(content=["Counter 2:"]),
      Counter(),
    ])

router = Router()
router.add_route("/", Outer)

app = App(router)
uvicorn.run(app)
