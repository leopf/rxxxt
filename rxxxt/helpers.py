from inspect import isawaitable
from typing import Awaitable, Callable, TypeVar, cast

T = TypeVar("T")
async def to_awaitable(fn: Callable[..., T | Awaitable[T]], *args, **kwargs) -> T:
  result = fn(*args, **kwargs)
  if isawaitable(result): result = await result
  return cast(T, result)
