import uvicorn, asyncio
from rxxxt import Component, local_state, App, El

class Counter(Component):
  count = local_state(int)
  someswitch = local_state(bool)

  async def on_init(self) -> None:
    self.add_worker(self.do_toggle())

  async def count_100(self):
    for _ in range(100):
      await asyncio.sleep(0.1)
      self.count += 1

  async def do_toggle(self):
    while True:
      self.someswitch = not self.someswitch
      await asyncio.sleep(1)

  def on_submit(self):
    self.add_job(self.count_100())

  def on_increment(self):
    self.count += 1

  def on_toggle_ws(self):
    self.context.use_websocket(not self.context.config.persistent)

  def render(self):
    return El.div(content=[
      El.div(content="on" if self.someswitch else "off"),
      El.div(content=f"count: {self.count}"),
      El.button(onclick=self.on_submit, content=["submit"]),
      El.button(onclick=self.on_increment, content=["increment"]),
      El.button(onclick=self.on_toggle_ws, content=["toggle ws"])
    ])

uvicorn.run(App(Counter))
