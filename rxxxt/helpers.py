from inspect import isawaitable
from typing import Callable, ParamSpec, TypeVar, cast, Any
from collections.abc import Awaitable

T = TypeVar("T")
FNP = ParamSpec('FNP')
FNR = TypeVar('FNR')

async def to_awaitable(fn: Callable[..., T | Awaitable[T]], *args: Any, **kwargs: Any) -> T:
  result = fn(*args, **kwargs)
  if isawaitable(result): result = await result
  return cast(T, result)
