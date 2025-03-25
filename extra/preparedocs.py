import shutil
import griffe

shutil.copyfile("README.md", "docs/index.md")

imports = list(griffe.load("rxxxt/__init__.py").imports.values())
imports.extend([
  "rxxxt.elements.ElementFactory",
  "rxxxt.state.StateResolver",
  "rxxxt.state.JWTStateResolver",
  "rxxxt.state.default_state_resolver",
  "rxxxt.events.ContextInputEventHandlerOptions"
])

imports.sort(key=lambda n: n.lower())

with open("docs/api.md", "w") as fd:
  fd.write("# API\n")
  for import_name in imports:
    fd.write(f"::: {import_name}\n")
