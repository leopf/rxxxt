from abc import ABC, abstractmethod
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
from io import BytesIO
import json
import os
import secrets
from typing import Any, Awaitable, Callable, Generic, Literal, TypeVar, cast, get_origin
from pydantic import TypeAdapter, ValidationError
import hmac

from rxxxt.component import Component
from rxxxt.execution import Context

T = TypeVar("T")
StateDataAdapter = TypeAdapter(dict[str, str])

class StateDescriptorBase(Generic[T], ABC):
  def __init__(self, default_factory: Callable[[], T], state_name: str | None = None) -> None:
    self._state_name = state_name
    self._default_factory = default_factory

    native_types = (bool, bytearray, bytes, complex, dict, float, frozenset, int, list, object, set, str, tuple)
    if default_factory in native_types or get_origin(default_factory) in native_types:
      self._val_type_adapter = TypeAdapter(default_factory)
    else:
      sig = inspect.signature(default_factory)
      self._val_type_adapter = TypeAdapter(sig.return_annotation)

  def __set_name__(self, owner, name):
    if self._state_name is None:
      self._state_name = name

  def __set__(self, obj, value):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")
    svalue = self._val_type_adapter.dump_json(value).decode("utf-8")
    obj.context.set_state(self._get_state_name(obj.context), svalue)

  def __get__(self, obj, objtype=None):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    svalue = obj.context.get_state(self._get_state_name(obj.context))
    if svalue is None: return self._default_factory()
    else: return cast(T, self._val_type_adapter.validate_json(svalue))

  @abstractmethod
  def _get_state_name(self, context: Context) -> str: pass

class StateDescriptor(StateDescriptorBase[T]):
  def __init__(self, is_global: bool, default_factory: Callable[[], T], state_name: str | None = None) -> None:
    super().__init__(default_factory, state_name)
    self._is_global = is_global

  def _get_state_name(self, context: Context):
    if self._state_name is None: raise ValueError("state name is not set!")
    if self._is_global: return f"global;{self._state_name}"
    else: return f"#local;{context.sid};{self._state_name}"

class ContextStateDescriptor(StateDescriptorBase[T]):
  def _get_state_name(self, context: Context):
    if self._state_name is None: raise ValueError("state name is not set!")
    state_key = None
    for sid in context.stack_sids:
      state_key = f"#context;{sid};{self._state_name}"
      if context.state_exists(state_key):
        return state_key
    if state_key is None: raise ValueError(f"State key not found for context '{self._state_name}'!")
    return state_key # this is just the key for context.sid

def local_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(False, default_factory, state_name=name)

def global_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(True, default_factory, state_name=name)

def context_state(default_factory: Callable[[], T], name: str | None = None):
  return ContextStateDescriptor(default_factory, state_name=name)

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

  def create_token(self, data: dict[str, str], old_token: str | None) -> str:
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

    try: state_data = StateDataAdapter.validate_python(payload["data"])
    except ValidationError as e: raise StateResolverError(e)
    return state_data

  @staticmethod
  def b64url_encode(value: bytes | bytearray): return base64.urlsafe_b64encode(value).rstrip(b"=")
  @staticmethod
  def b64url_decode(value: bytes | bytearray): return base64.urlsafe_b64decode(value + b"=" * (4 - len(value) % 4))

def default_state_resolver() -> JWTStateResolver:
  """
  Creates a JWTStateResolver.
  Uses the environment variable `JWT_SECRET` as its secret, if set, otherwise creates a new random, temporary secret.
  """

  jwt_secret = os.getenv("JWT_SECRET", None)
  if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
  else: jwt_secret = jwt_secret.encode("utf-8")
  return JWTStateResolver(jwt_secret)
