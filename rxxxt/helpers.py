import hmac
from inspect import isawaitable
from typing import Callable, ParamSpec, TypeVar, cast, Any, Literal
from collections.abc import Awaitable
import re, functools, hashlib, io, base64, json
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, TypeAdapter

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

def attribute_key_to_event_name(original_key: str):
  return original_key[2:] if original_key.startswith("on") else original_key

class JWTError(Exception): pass

class JWTManager:
  class JWTHeader(BaseModel):
    typ: Literal["JWT"]
    alg: str

  class JWTPayloadValidations(BaseModel):
    exp: int

    def is_valid(self):
      expires_dt = datetime.fromtimestamp(self.exp, timezone.utc)
      return expires_dt >= datetime.now(tz=timezone.utc)

  JWTPayloadAdapter = TypeAdapter(dict[str, Any])

  def __init__(self, secret: bytes, max_age: timedelta, algorithm: str = "HS512") -> None:
    super().__init__()
    self._secret = secret
    self._max_age: timedelta = max_age
    self._algorithm = algorithm
    self._digest = { "HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512 }[algorithm]
    self._jwt_header = JWTManager.encode_json({ "typ": "JWT", "alg": self._algorithm }) + b"."

  def sign(self, extra_fields: dict[str, Any]):
    try:
      expires_at = int((datetime.now(tz=timezone.utc) + self._max_age).timestamp())
      stream = io.BytesIO()
      _ = stream.write(self._jwt_header)
      _ = stream.write(JWTManager.encode_json({ "exp": expires_at, **extra_fields }))
      signature = hmac.digest(self._secret, stream.getvalue(), self._digest)
      _ = stream.write(b".")
      _ = stream.write(JWTManager.b64_url_encode(signature))
      return stream.getvalue().decode()
    except Exception as e:
      if not isinstance(e, JWTError): raise JWTError(e)
      else: raise e

  def verify(self, token: str):
    try:
      parts = token.encode().split(b".")
      if len(parts) != 3: raise JWTError("invalid format (expected 3 parts)")

      header = JWTManager.JWTHeader.model_validate_json(JWTManager.b64_url_decode(parts[0]))
      if header.alg != self._algorithm: raise JWTError("invalid algorithm in header")

      ref_signature = hmac.digest(self._secret, parts[0] + b"." + parts[1], self._digest)
      if not hmac.compare_digest(JWTManager.b64_url_decode(parts[2]), ref_signature):
        raise JWTError("invalid JWT signature!")

      full_payload = JWTManager.JWTPayloadAdapter.validate_json(JWTManager.b64_url_decode(parts[1]))
      if not JWTManager.JWTPayloadValidations.model_validate(full_payload).is_valid():
        raise JWTError("token expired")

      full_payload.pop("exp", None)
      return full_payload
    except Exception as e:
      if not isinstance(e, JWTError): raise JWTError(e)
      else: raise e

  @staticmethod
  def encode_json(obj: Any):
    return JWTManager.b64_url_encode(json.dumps(obj).encode())

  @staticmethod
  def b64_url_encode(value: bytes | bytearray):
    return base64.urlsafe_b64encode(value).rstrip(b"=")

  @staticmethod
  def b64_url_decode(value: bytes | bytearray):
    return base64.urlsafe_b64decode(value + b"=" * (4 - len(value) % 4))
