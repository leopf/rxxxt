from rxxxt import Component, event_handler, Element, App, El, UnescapedHTMLElement, PageBuilder
import uvicorn

class Main(Component):
  @event_handler()
  def on_click(self):
    self.context.emit("download", { "url": "https://github.com/leopf/rxxxt/archive/refs/heads/master.zip", "name": "master.zip" })

  def render(self) -> Element:
    return El.button(onclick=self.on_click, content=["download"])

page_builder = PageBuilder()

page_builder.add_body_end(El.script(content=[UnescapedHTMLElement("""
rxxxt.on("download", data => {
  const dlElement = document.createElement("a");
  dlElement.download = data.name;
  dlElement.href = data.url;
  dlElement.style.display = "none";
  document.body.appendChild(dlElement);
  dlElement.click();
});
""")]))

app = App(Main, page_factory=page_builder)
uvicorn.run(app)
