# Debugging

Enable verbose error logs by configuring Python's logger before running the server:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

With the debug log level, rxxxt will print traces when something errors.
