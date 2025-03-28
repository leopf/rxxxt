from rxxxt import Component, local_state, App, event_handler, El, VEl, PageBuilder, local_state_box
from typing import Annotated
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
import uvicorn
import ollama
import os

MODEL_NAME = os.getenv("MODEL_NAME", "phi3.5:latest")

class Chat(Component):
  messages = local_state_box(list[ollama.Message])
  current_message = local_state(str)
  generating = local_state(bool)

  async def on_init(self) -> None:
    self.context.use_websocket()

  async def generate_response(self):
    gen_opts = ollama.Options(num_predict=500)
    response = await ollama.AsyncClient().chat(MODEL_NAME, self.messages.value[:-1], stream=True, options=gen_opts)
    async for part in response:
      with self.messages:
        self.messages.value[-1].content = (self.messages.value[-1].content or "") + (part.message.content or "")
    self.generating = False

  @event_handler(prevent_default=True)
  def on_message(self):
    with self.messages:
      self.messages.value.append(ollama.Message(role="user", content=self.current_message))
      self.messages.value.append(ollama.Message(role="assistant", content=""))

    self.current_message = ""
    self.generating = True

    self.add_job(self.generate_response())

  @event_handler(debounce=500, throttle=500)
  def on_message_input(self, text: Annotated[str, "target.value"]):
    self.current_message = text

  def render(self):
    return El.div(_class="content", content=[
      El.div(_class="messages", content=[
        self._render_message(msg) for msg in self.messages.value
      ]),
      self._render_user_input()
    ])

  def _render_message(self, message: ollama.Message):
    return El.div(_class=f"message message--{message.role}", content=[message.content or ""])

  def _render_user_input(self):
    return El.form(onsubmit=self.on_message, _class="user-input", content=[
      VEl.input(oninput=self.on_message_input, value=self.current_message),
      El.button(disabled=self.generating, content=["submit"])
    ])

page_factory = PageBuilder()
page_factory.add_stylesheet("/assets/main.css")

server = FastAPI()
server.mount("/assets", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "assets")))
server.mount("/", App(Chat, page_factory=page_factory))
uvicorn.run(server)
