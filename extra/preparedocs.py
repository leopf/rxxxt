import shutil
import griffe

_ = shutil.copyfile("README.md", "docs/index.md")

module = griffe.load("rxxxt/__init__.py")
imports = set(module.imports.values())
imports.update([
  "rxxxt.execution.State",
  "rxxxt.state.StateResolver",
  "rxxxt.state.JWTStateResolver",
  "rxxxt.component.StateBox",
  "rxxxt.state.default_state_resolver",
  "rxxxt.helpers.match_path",
  "rxxxt.helpers.JWTManager",
  "rxxxt.helpers.JWTError",
  "rxxxt.events.InputEventDescriptorOptions",
  "rxxxt.asgi.TransportContext",
  "rxxxt.asgi.HTTPContext",
  "rxxxt.asgi.WebsocketContext",
  "rxxxt.asgi.http_handler",
  "rxxxt.asgi.websocket_handler",
  "rxxxt.asgi.routed_handler",
  "rxxxt.asgi.http_not_found_handler",
  "rxxxt.asgi.Composer",
  "rxxxt.asgi.ASGIScope",
  "rxxxt.asgi.ASGIFnReceive",
  "rxxxt.asgi.ASGIFnSend",
  "rxxxt.asgi.ASGIHandler",
  "rxxxt.asgi.ASGINextException",
])

imports = sorted(imports, key=lambda n: n.lower())

with open("docs/api.md", "w") as fd:
  _ = fd.write("# API\n")
  for import_name in imports:
    _ = fd.write(f"::: {import_name}\n")
