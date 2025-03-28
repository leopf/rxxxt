from io import StringIO
import sys
import ollama
import os
from pathlib import Path

MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:12b")

md_path = "mdsite/"
file_texts = StringIO()

for f in Path(md_path).rglob("**/*.md"):
  if "api" in str(f): continue
  file_texts.write(f"\n\n----- filename: {os.path.relpath(f, md_path)}-----\n")
  with open(f, "rt") as fd:
    file_texts.write(fd.read())

response = ollama.chat(MODEL_NAME, [
  ollama.Message(role="system", content="""
- you help the user write docs
- be precise and technical
- do not answer the user, except for the markdown he asks for, no acknowledgements whatsoever
""".strip()),
  ollama.Message(role="user", content=f"""
{file_texts.getvalue()}
----
Write a chronological and detailed tutorial for rxxxt from front to back.
""".strip())
], stream=True)

with open("playground/tutorial.md", "wt") as final_response:
  for part in response:
    final_response.write(part.message.content or "")
    sys.stdout.write(part.message.content or "")
    sys.stdout.flush()
