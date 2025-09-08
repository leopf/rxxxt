from inspect import isawaitable
from typing import Callable, ParamSpec, TypeVar, cast, Any
from collections.abc import Awaitable
import re, functools

T = TypeVar("T")
FNP = ParamSpec('FNP')
FNR = TypeVar('FNR')

async def to_awaitable(fn: Callable[..., T | Awaitable[T]], *args: Any, **kwargs: Any) -> T:
  result = fn(*args, **kwargs)
  if isawaitable(result): result = await result
  return cast(T, result)

_RE_PATH_PARAM_DEF = re.compile(r"\{([^\*\}]*)(\*)?\}")
_RE_PATH_VALID = re.compile(r"[A-Za-z0-9._~\-\/]*")
_RE_PATH_PART_VALID = re.compile(r"[A-Za-z0-9._~\-]*")

@functools.lru_cache()
def _compile_matcher(pattern: str, re_flags: int):
  re_parts: list[str] = []
  index = 0
  for m in _RE_PATH_PARAM_DEF.finditer(pattern):
    segment = pattern[index:m.start()]
    if not _RE_PATH_VALID.fullmatch(segment):
      raise ValueError(f"path segment '{segment}' in '{pattern}' is invalid!")
    re_parts.append(re.escape(segment))

    if str.isidentifier(m.group(1)):
      if m.group(2) == "*": re_parts.append(f"(?P<{m.group(1)}>{_RE_PATH_VALID.pattern})")
      else: re_parts.append(f"(?P<{m.group(1)}>{_RE_PATH_PART_VALID.pattern})")
    elif m.group(1) == "":
      if m.group(2) == "*": re_parts.append(f"({_RE_PATH_VALID.pattern})")
      else: re_parts.append(f"({_RE_PATH_PART_VALID.pattern})")
    else:
      raise ValueError(f"'{m.group(1)}' is not a valid part name in '{pattern}'!")

    index = m.end()

  final_segment = pattern[index:]
  if not _RE_PATH_VALID.fullmatch(final_segment):
    raise ValueError(f"path segment '{final_segment}' in '{pattern}' is invalid!")
  re_parts.append(re.escape(final_segment))

  pat_re = re.compile("".join(re_parts), re_flags)

  def _matcher(path: str) -> dict[str, str] | None:
    match = pat_re.fullmatch(path)
    if match is None: return None
    else: return match.groupdict()
  return _matcher

def match_path(pattern: str, path: str, re_flags: int = re.IGNORECASE):
  return _compile_matcher(pattern, re_flags)(path)
