from inspect import isawaitable
from typing import Callable, TypeVar, cast, Any
from collections.abc import Awaitable

T = TypeVar("T")
async def to_awaitable(fn: Callable[..., T | Awaitable[T]], *args: Any, **kwargs: Any) -> T:
  result = fn(*args, **kwargs)
  if isawaitable(result): result = await result
  return cast(T, result)
