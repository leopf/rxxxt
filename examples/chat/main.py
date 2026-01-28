import ollama, os, typing, uvicorn, asyncio
from typing import List
from rxxxt import Component, local_state, event_handler, El, VEl, PageBuilder, SharedExternalState, App
from rxxxt.asgi import Composer, HTTPContext, http_handler, routed_handler

MODEL_NAME = os.getenv("MODEL_NAME", "llama3.2:3b")

def icon_send():
  return El.svg(
    xmlns="http://www.w3.org/2000/svg",
    width="24",
    height="24",
    viewBox="1 0 24 24",
    fill="none",
    stroke="white",
    stroke_width="2",
    stroke_linecap="round",
    stroke_linejoin="round",
    _class="feather feather-send",
    content=[
      El.line(x1="22", y1="2", x2="11", y2="13"),
      El.polygon(points="22 2 15 22 11 13 2 9 22 2"),
    ],
  )

class Chat(Component):
  messages: SharedExternalState[List[ollama.Message]] = SharedExternalState([])
  current_message = local_state(str)
  generating = local_state(bool)

  async def on_init(self):
    self.context.use_websocket()

  async def generate_response(self):
    self.generating = True

    if os.getenv("MOCK") == "1":
      await asyncio.sleep(0.5)
      response_text = "This is a mocked response from a fake ollama service."
      for word in response_text.split():
        self.messages.value[-1]["content"] = (self.messages.value[-1].get("content") or "") + word + " "
        self.messages.update()
        await asyncio.sleep(0.1)
    else:
      gen_opts = ollama.Options(num_predict=500)
      response = await ollama.AsyncClient().chat(
        MODEL_NAME, self.messages.value[:-1], stream=True, options=gen_opts
      )
      async for part in response:
        self.messages.value[-1]["content"] = (self.messages.value[-1].get("content") or "") + (
          part.get("message", {}).get("content") or ""
        )
        self.messages.update()

    self.generating = False

  @event_handler(prevent_default=True)
  def on_message(self):
    if not self.current_message:
      return
    self.messages.value.append(ollama.Message(role="user", content=self.current_message))
    self.current_message = ""
    self.messages.value.append(ollama.Message(role="assistant", content=""))
    self.messages.update()
    self.add_job(self.generate_response())

  @event_handler(debounce=500, throttle=500)
  def on_message_input(self, text: typing.Annotated[str, "target.value"]):
    self.current_message = text

  def render(self):
    return El.div(
      _class="content",
      content=[
        El.div(
          _class="messages",
          content=[self._render_message(msg) for msg in self.messages.value],
        ),
        self._render_user_input(),
      ],
    )

  def _render_message(self, message: ollama.Message):
    return El.div(
      _class=f"message message--{message.get('role')}",
      content=[
        El.strong(content=[f"{message.get('role')}: "]),
        message.get("content") or "",
      ],
    )

  def _render_user_input(self):
    return El.form(
      onsubmit=self.on_message,
      _class="user-input",
      content=[
        VEl.input(
          oninput=self.on_message_input,
          value=self.current_message,
          placeholder="Type a message...",
        ),
        El.button(disabled=self.generating, content=[icon_send()]),
      ],
    )

page_factory = PageBuilder()
page_factory.add_stylesheet("/assets/main.css")
page_factory.add_header(El.title(content=[f"Chat with {MODEL_NAME}"]))

composer = Composer()

@composer.add_handler
@http_handler
@routed_handler("/assets/main.css")
async def _(ctx: HTTPContext, _):
  await ctx.respond_file(os.path.join(os.path.dirname(__file__), "assets", "main.css"))

composer.add_handler(App(Chat, page_factory=page_factory))

if __name__ == "__main__":
  uvicorn.run(composer)
