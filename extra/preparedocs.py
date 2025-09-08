import shutil
import griffe

_ = shutil.copyfile("README.md", "docs/index.md")

imports = list(griffe.load("rxxxt/__init__.py").imports.values())
imports.extend([
  "rxxxt.execution.State",
  "rxxxt.state.StateResolver",
  "rxxxt.state.JWTStateResolver",
  "rxxxt.state.default_state_resolver",
  "rxxxt.helpers.match_path",
  "rxxxt.events.ContextInputEventHandlerOptions"
])

imports.sort(key=lambda n: n.lower())

with open("docs/api.md", "w") as fd:
  _ = fd.write("# API\n")
  for import_name in imports:
    _ = fd.write(f"::: {import_name}\n")
