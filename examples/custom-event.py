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
  const link = document.createElement("a");
  link.download = data.name;
  link.href = data.url;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
});
""")]))

app = App(Main, page_factory=page_builder)
uvicorn.run(app)
