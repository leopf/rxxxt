import uvicorn, asyncio, logging
from rxxxt import App, Component, PageBuilder, local_state, El, VEl, event_handler
from typing import Annotated

logging.basicConfig(level=logging.DEBUG)

waiting_futures: list[asyncio.Future] = []
messages: list[tuple[str, str]] = []

class Main(Component):
  message = local_state(str)
  username = local_state(str)

  @property
  def message_allowed(self):
    return not not self.message and not not self.username.strip()

  @event_handler(debounce=500)
  def on_message_input(self, value: Annotated[str, "target.value"]):
    self.message = value

  @event_handler(debounce=500)
  def on_username_input(self, value: Annotated[str, "target.value"]):
    self.username = value.strip()

  @event_handler(prevent_default=True)
  def send_message(self):
    if not self.message_allowed:
      return

    global messages, waiting_futures
    messages.append((self.username, self.message))
    resolving_futures = waiting_futures
    waiting_futures = []
    for fut in resolving_futures:
      fut.set_result(0)
    self.message = ""


  async def message_update_loop(self):
    while True:
      fut = asyncio.Future()
      waiting_futures.append(fut)
      await fut
      self.context.request_update()

  async def on_init(self):
    self.context.use_websocket()
    self.add_worker(self.message_update_loop())

  def render(self):
    return El.div(_class="content", content=[
      El.div(style="font-size: 0.9rem;", content=["your name:"]),
      VEl.input(_type="text", value=self.username, oninput=self.on_username_input, placeholder="username", style="display: block;"),
      El.div(style="flex: 1; padding: 1rem 0;", content=[ El.div(content=[f"{username}: {message}"]) for username, message in messages ]),
      El.form(style="display: flex; gap: 0.5rem; align-items: center;", onsubmit=self.send_message, content=[
        VEl.input(_type="text", value=self.message, oninput=self.on_message_input, placeholder="new message", style="display: block; flex: 1"),
        El.button(disabled=not self.message_allowed, content=["send"])
      ])
    ])

page_factory = PageBuilder()
page_factory.add_header(El.style(content=[
"""
body {
  margin: 0;
  font-family: sans-serif;
}
.content {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  height: 100vh;
  padding: 1rem;
  box-sizing: border-box;
}
"""
]))

app = App(Main, page_factory=page_factory)
uvicorn.run(app)
