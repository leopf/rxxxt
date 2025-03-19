import shutil
import griffe

shutil.copyfile("README.md", "docs/index.md")

imports = list(griffe.load("rxxxt/__init__.py").imports.items())
imports.sort(key=lambda i: i[0].lower())

with open("docs/api.md", "w") as fd:
  fd.write("# API\n")
  for _, import_name in imports:
    fd.write(f"::: {import_name}\n")
