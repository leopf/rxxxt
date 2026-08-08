# TODO

## 1. Make the server log its serving
`HTTPServer.run()` should log when it starts listening (and ideally per-request / connect info) so it's visible that it's serving. Check `log_level` config.

## 2. Update all examples and docs
- Update `examples/*.py` that use `import uvicorn` / `uvicorn.run(...)` to use the built-in `HTTPServer` instead:
  - `examples/counter.py` (done — but verify and keep consistent)
  - `examples/with-fastapi.py`
  - others that start a server (chat, todo, etc.)
- Update `README.md` (currently mentions installing/running uvicorn).
- Update `docs/` referencing uvicorn as the serving method.
- Goal: "want to use the integrated server for this kinda stuff in the future" — make the built-in server the documented default.

## 3. Factor out lifecycle handling
Lifecycle (startup/shutdown handshake + `state` namespace) currently lives inline in `HTTPServer` (`_lifespan_startup` / `_lifespan_shutdown`). It feels out of place in the server class. Factor it into its own component/module (e.g. a `LifespanContext` / separate class) and have the server use it.

## 4. Import style: use inline imports (one import per line)
Update imports to inline style like:
```python
import asyncio
import base64
import dataclasses
import hashlib
import http.client
import logging
import signal
import ssl
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Protocol, cast
from rxxxt.asgi import ASGIHandler, ASGIScope
```
Applies to `rxxxt/httpserver.py` (and any other files using compact/joined imports).
