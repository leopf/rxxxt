from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import sys
from typing import Awaitable, ByteString, Literal, get_type_hints
from pydantic import BaseModel
import hmac

class State(BaseModel): pass

@dataclass
class PartialStateInfo:
  is_global: bool
  name: str | None

@dataclass
class StateInfo:
  is_global: bool
  attr_name: str
  state_name: str
  state_type: type[State]

def global_state(name: str | None = None): return PartialStateInfo(is_global=True, name=name)

def get_state_infos_for_object_type(t: type[object]):
  global_ns = vars(sys.modules[t.__module__])
  for base_class in reversed(t.__mro__):
    type_hints = get_type_hints(base_class, globalns=global_ns)
    for attr_name, attr_type in type_hints.items():
      if isinstance(attr_type, type) and issubclass(attr_type, State):
        if hasattr(t, attr_name):
          partial_state_info = getattr(t, attr_name)
          if not isinstance(partial_state_info, PartialStateInfo):
            raise ValueError("State field must not be defined as anything but a PartialStateInfo in the class.")
          yield StateInfo(is_global=partial_state_info.is_global, attr_name=attr_name, state_name=partial_state_info.name or attr_name, state_type=attr_type)
        else:
          yield StateInfo(is_global=False, state_name=attr_name, attr_name=attr_name, state_type=attr_type)

class StateResolverError(BaseException): pass

class StateResolver(ABC):
  @abstractmethod
  def create_token(self, data: dict[str, str], old_token: str | None) -> str | Awaitable[str]: pass
  @abstractmethod
  def resolve(self, token: str) -> dict[str, str] | Awaitable[dict[str, str]]: pass

class JWTStateResolver(StateResolver):
  def __init__(self, secret: bytes, max_age: timedelta | None = None, algorithm: Literal["HS256"] | Literal["HS384"] | Literal["HS512"] = "HS512") -> None:
    super().__init__()
    self.secret = secret
    self.algorithm = algorithm
    self.digest = { "HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512 }[algorithm]
    self.max_age: timedelta = timedelta(days=1) if max_age is None else max_age

  def create_token(self, data: dict[str, str], _: str | None) -> str:
    payload = { "exp": int((datetime.now(tz=timezone.utc) + self.max_age).timestamp()), "data": data }
    stream = BytesIO()
    stream.write(JWTStateResolver.b64url_encode(json.dumps({
      "typ": "JWT",
      "alg": self.algorithm
    }).encode("utf-8")))
    stream.write(b".")
    stream.write(JWTStateResolver.b64url_encode(json.dumps(payload).encode("utf-8")))

    signature = hmac.digest(self.secret, stream.getvalue(), self.digest)
    stream.write(b".")
    stream.write(JWTStateResolver.b64url_encode(signature))
    return stream.getvalue().decode("utf-8")

  def resolve(self, token: str) -> dict[str, str] | Awaitable[dict[str, str]]:
    rtoken = token.encode("utf-8")
    sig_start = rtoken.rfind(b".")
    if sig_start == -1: raise StateResolverError("Invalid token format")
    parts = rtoken.split(b".")
    if len(parts) != 3: raise StateResolverError("Invalid token format")

    try: header = json.loads(JWTStateResolver.b64url_decode(parts[0]))
    except: raise StateResolverError("Invalid token header")

    if not isinstance(header, dict) or header.get("typ", None) != "JWT" or header.get("alg", None) != self.algorithm:
      raise StateResolverError("Invalid header contents")

    signature = JWTStateResolver.b64url_decode(rtoken[(sig_start + 1):])
    actual_signature = hmac.digest(self.secret, rtoken[:sig_start], self.digest)
    if not hmac.compare_digest(signature, actual_signature):
      raise StateResolverError("Invalid JWT signature!")

    payload = json.loads(JWTStateResolver.b64url_decode(parts[1]))
    if not isinstance(payload, dict) or not isinstance(payload.get("exp", None), int) or not isinstance(payload.get("data", None), dict):
      raise StateResolverError("Invalid JWT payload!")

    expires_dt = datetime.fromtimestamp(payload["exp"], timezone.utc)
    if expires_dt < datetime.now(tz=timezone.utc):
      raise StateResolverError("JWT expired!")

    return payload["data"]

  @staticmethod
  def b64url_encode(value: ByteString): return base64.urlsafe_b64encode(value).rstrip(b"=")
  @staticmethod
  def b64url_decode(value: ByteString): return base64.urlsafe_b64decode(value + b"=" * (4 - len(value) % 4))
