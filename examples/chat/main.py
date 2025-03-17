from rxxxt import Component, local_state, App, event_handler, El, VEl, PageBuilder
from typing import Annotated
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
import asyncio
import uvicorn
import ollama
import os

MODEL_NAME = os.getenv("MODEL_NAME", "phi3.5:latest")

class Chat(Component):
  messages = local_state(list[ollama.Message])
  current_message = local_state(str)
  generating = local_state(bool)

  async def on_init(self) -> None:
    self.context.use_websocket()

  async def generate_response(self):
    result = await asyncio.to_thread(ollama.chat, MODEL_NAME, self.messages, options=ollama.Options(num_predict=500))
    self.messages += [result.message]
    self.generating = False

  @event_handler(prevent_default=True)
  def on_message(self):
    self.messages += [ ollama.Message(role="user", content=self.current_message) ]
    self.current_message = ""
    self.generating = True
    self.add_background_task(self.generate_response())

  @event_handler(throttle=500, debounce=500)
  def on_message_input(self, text: Annotated[str, "target.value"]):
    self.current_message = text

  def render(self):
    return El.div(_class="content", content=[
      El.div(_class="messages", content=[
        self._render_message(msg) for msg in self.messages
      ]),
      self._render_user_input()
    ])

  def _render_message(self, message: ollama.Message):
    return El.div(_class=f"message message--{message.role}", content=[message.content or ""])

  def _render_user_input(self):
    return El.form(onsubmit=self.on_message, _class="user-input", content=[
      VEl.input(oninput=self.on_message_input, value=self.current_message), El.button(disabled=self.generating, content=["submit"])
    ])

page_layout = PageBuilder()
page_layout.add_header(VEl.link(rel="stylesheet", href="/assets/main.css"))

server = FastAPI()
server.mount("/assets", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "assets")))
server.mount("/", App(Chat, page_layout=page_layout))
uvicorn.run(server)
