from abc import ABC, abstractmethod
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import sys
from typing import TYPE_CHECKING, Any, Awaitable, ByteString, Callable, Literal, get_type_hints
from pydantic import BaseModel
import hmac

if TYPE_CHECKING:
  from rxxxt.execution import Context

class StateBase(ABC):
  def init(self, context: 'Context') -> None | Awaitable[None]: pass

  @abstractmethod
  def get_value(self) -> Any: pass
  def set_value(self, value: Any) -> None: pass
  @abstractmethod
  def to_json(self) -> str: pass

StateMaker = Callable[[str | None], StateBase]

class State(StateBase, BaseModel):
  def to_json(self) -> str: return self.model_dump_json()
  def get_value(self) -> Any: return self
  @classmethod
  def state_maker(cls, json_data: str | None):
    if json_data is None: return cls()
    else: return cls.model_validate_json(json_data)

class StateField(StateBase):
  def __init__(self, value: Any) -> None:
    super().__init__()
    self.value = value

  def get_value(self) -> Any: return self.value
  def set_value(self, value: Any) -> None: self.value = value
  def to_json(self) -> str: return json.dumps(self.value)

@dataclass
class StateInfo:
  is_global: bool
  attr_name: str
  state_name: str
  state_maker: StateMaker

@dataclass
class PartialStateInfo:
  is_global: bool
  name: str | None

@dataclass
class StateFieldInfo:
  default_value: Any = None
  default_facotry: None | Callable[[], Any] = None

  def state_maker(self, json_data: str | None):
    if json_data is None:
      if self.default_value is not None: return StateField(self.default_value)
      elif self.default_facotry is not None: return StateField(self.default_facotry())
      else: return StateField(None)
    else: return StateField(json.loads(json_data))

def state_field(default_value: Any = None, default_facotry: None | Callable[[], Any] = None):
  return StateFieldInfo(default_value=default_value, default_facotry=default_facotry)
def global_state(name: str | None = None): return PartialStateInfo(is_global=True, name=name)

def get_state_infos_for_object_type(t: type[object]):
  global_ns = vars(sys.modules[t.__module__])
  for base_class in reversed(t.__mro__):
    type_hints = get_type_hints(base_class, globalns=global_ns)
    for attr_name, attr_type in type_hints.items():
      attr_value = getattr(t, attr_name, None)
      if isinstance(attr_type, type) and issubclass(attr_type, State):
        if hasattr(t, attr_name):
          if not isinstance(attr_value, PartialStateInfo):
            raise ValueError("State field must not be defined as anything but a PartialStateInfo in the class.")
          yield StateInfo(is_global=attr_value.is_global, attr_name=attr_name, state_name=attr_value.name or attr_name, state_maker=attr_type.state_maker)
        else:
          yield StateInfo(is_global=False, state_name=attr_name, attr_name=attr_name, state_maker=attr_type.state_maker)
      elif isinstance(attr_value, StateFieldInfo):
        yield StateInfo(is_global=False, attr_name=attr_name, state_name=attr_name, state_maker=attr_value.state_maker)

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
