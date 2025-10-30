import uvicorn, os, json, typing, asyncio
from rxxxt import Component, App, El, PageBuilder
from rxxxt.asgi import Composer, HTTPContext, http_handler, routed_handler
from rxxxt.elements import HTMLAttributeValue, add_attributes

def chart(*, config: dict[str, typing.Any], **kwargs: HTMLAttributeValue):
  return El["chart-js"](content=[], **add_attributes(kwargs, config=json.dumps(config)))

class Dashboard(Component):
  async def load_data(self):
    await asyncio.sleep(0.1) # this is mean to illustrate loading data from db
    return { "labels": [ "A", "B", "C" ], "datasets": [ { "label": "Demo", "data": [ 3, 7, 4 ] } ] }

  async def render(self):
    return El.div(_class="dashboard", content=[
      chart(config={
        "type": "bar",
        "data": await self.load_data()
      }, style="height: 33vh;"),
      chart(config={
        "type": "line",
        "data": await self.load_data()
      }, style="height: 33vh;"),
      chart(config={
        "type": "pie",
        "data": await self.load_data()
      }, style="height: 33vh;"),
    ])

composer = Composer()

@composer.add_handler
@http_handler
@routed_handler("/{filename}")
async def _(ctx: HTTPContext, params: dict[str, str]):
  filename = params["filename"]
  if filename not in ("main.css", "main.js"):
    return ctx.next()
  await ctx.respond_file(os.path.join(os.path.dirname(__file__), filename))

page_factory = PageBuilder()
page_factory.add_stylesheet("/main.css")
page_factory.add_body_script("/main.js", type="module")

_ = composer.add_handler(App(Dashboard, page_factory=page_factory))

uvicorn.run(composer)
