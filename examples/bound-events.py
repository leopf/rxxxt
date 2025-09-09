import json
from typing import Annotated
from rxxxt import Component, event_handler, El, Element, App, VEl, local_state_box
import uvicorn

import logging
logging.basicConfig(level=logging.DEBUG)

class Main(Component):
  texts = local_state_box(dict[str, str])

  @event_handler(debounce=500, throttle=500)
  def on_input(self, name: str, value: Annotated[str, "target.value"]):
    self.texts.value[name] = value
    self.texts.update()

  def render(self) -> Element:
    return El.div(content=[
      El.div(content=[ json.dumps(self.texts.value) ]),
      *(VEl.input(value=self.texts.value.get(name, ""), oninput=self.on_input.bind(name=name)) for name in ("field_a", "field_b"))
    ])

app = App(Main)
uvicorn.run(app)
