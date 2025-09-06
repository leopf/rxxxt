from abc import ABC, abstractmethod
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
from io import BytesIO
import json
import os
import secrets
from typing import Callable, Generic, get_origin, Any
from collections.abc import Awaitable
from pydantic import TypeAdapter, ValidationError
import hmac

from rxxxt.cell import SerilializableStateCell
from rxxxt.component import Component
from rxxxt.execution import Context, State
from rxxxt.helpers import T

StateDataAdapter = TypeAdapter(dict[str, str])

class StateBox(Generic[T]):
  def __init__(self, key: str, state: State, inner: SerilializableStateCell[T]) -> None:
    super().__init__()
    self._key = key
    self._state = state
    self._inner = inner

  def __enter__(self): return self
  def __exit__(self, *_): self.update()

  @property
  def key(self): return self._key

  @property
  def value(self): return self._inner.value

  @value.setter
  def value(self, v: T):
    self._inner.value = v
    self.update()

  def update(self): self._state.request_key_updates({ self._key })

class StateBoxDescriptorBase(Generic[T]):
  def __init__(self, state_key_producer: Callable[[Context, str], str], default_factory: Callable[[], T], state_name: str | None = None) -> None:
    self._state_name = state_name
    self._default_factory = default_factory
    self._state_key_producer = state_key_producer

    native_types = (bool, bytearray, bytes, complex, dict, float, frozenset, int, list, object, set, str, tuple)
    if default_factory in native_types or get_origin(default_factory) in native_types:
      self._val_type_adapter: TypeAdapter[Any] = TypeAdapter(default_factory)
    else:
      sig = inspect.signature(default_factory)
      self._val_type_adapter = TypeAdapter(sig.return_annotation)

  def __set_name__(self, owner: Any, name: str):
    if self._state_name is None:
      self._state_name = name

  def _get_box(self, context: Context) -> StateBox[T]:
    if not self._state_name: raise ValueError("State name not defined!")
    key = self._state_key_producer(context, self._state_name)

    if (cell:=context.state.get_key_cell(key)) is not None:
      if not isinstance(cell, SerilializableStateCell):
        raise ValueError(f"Cell is not serializable for key '{key}'!")
      return StateBox(key, context.state, cell)

    old_str_value = context.state.get_key_str(key)
    if old_str_value is None:
      value = self._default_factory()
    else:
      value = self._val_type_adapter.validate_json(old_str_value)
    cell = SerilializableStateCell(value, lambda v: self._val_type_adapter.dump_json(v).decode("utf-8"))
    context.state.set_key_cell(key, cell)
    return StateBox(key, context.state, cell)

class StateBoxDescriptor(StateBoxDescriptorBase[T]):
  def __get__(self, obj: Any, objtype: Any=None):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    obj.context.subscribe(box.key)

    return box

class StateDescriptor(StateBoxDescriptorBase[T]):
  def __set__(self, obj: Any, value: Any):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    box.value = value

  def __get__(self, obj: Any, objtype: Any=None):
    if not isinstance(obj, Component):
      raise TypeError("StateDescriptor used on non-component!")

    box = self._get_box(obj.context)
    obj.context.subscribe(box.key)

    return box.value

def get_global_state_key(_context: Context, name: str):
  return f"global;{name}"

def get_local_state_key(context: Context, name: str):
  return f"#local;{context.sid};{name}"

def get_context_state_key(context: Context, name: str):
  state_key = None
  exisiting_keys = context.state.keys
  for sid in context.stack_sids:
    state_key = f"#context;{sid};{name}"
    if state_key in exisiting_keys:
      return state_key
  if state_key is None: raise ValueError(f"State key not found for context '{name}'!")
  return state_key # this is just the key for context.sid

def local_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_local_state_key, default_factory, state_name=name)

def global_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_global_state_key, default_factory, state_name=name)

def context_state(default_factory: Callable[[], T], name: str | None = None):
  return StateDescriptor(get_context_state_key, default_factory, state_name=name)

def local_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_local_state_key, default_factory, state_name=name)

def global_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_global_state_key, default_factory, state_name=name)

def context_state_box(default_factory: Callable[[], T], name: str | None = None):
  return StateBoxDescriptor(get_context_state_key, default_factory, state_name=name)

class StateResolverError(BaseException): pass

class StateResolver(ABC):
  @abstractmethod
  def create_token(self, data: dict[str, str], old_token: str | None) -> str | Awaitable[str]: pass
  @abstractmethod
  def resolve(self, token: str) -> dict[str, str] | Awaitable[dict[str, str]]: pass

class JWTStateResolver(StateResolver):
  def __init__(self, secret: bytes, max_age: timedelta | None = None, algorithm: str = "HS512") -> None:
    super().__init__()
    self._secret = secret
    self._algorithm = algorithm
    self._digest = { "HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512 }[algorithm]
    self._max_age: timedelta = timedelta(days=1) if max_age is None else max_age

  def create_token(self, data: dict[str, str], old_token: str | None) -> str:
    payload = { "exp": int((datetime.now(tz=timezone.utc) + self._max_age).timestamp()), "data": data }
    stream = BytesIO()
    _ = stream.write(JWTStateResolver._b64url_encode(json.dumps({
      "typ": "JWT",
      "alg": self._algorithm
    }).encode("utf-8")))
    _ = stream.write(b".")
    _ = stream.write(JWTStateResolver._b64url_encode(json.dumps(payload).encode("utf-8")))

    signature = hmac.digest(self._secret, stream.getvalue(), self._digest)
    _ = stream.write(b".")
    _ = stream.write(JWTStateResolver._b64url_encode(signature))
    return stream.getvalue().decode("utf-8")

  def resolve(self, token: str) -> dict[str, str]:
    rtoken = token.encode("utf-8")
    sig_start = rtoken.rfind(b".")
    if sig_start == -1: raise StateResolverError("Invalid token format")
    parts = rtoken.split(b".")
    if len(parts) != 3: raise StateResolverError("Invalid token format")

    try: header = json.loads(JWTStateResolver._b64url_decode(parts[0]))
    except: raise StateResolverError("Invalid token header")

    if not isinstance(header, dict) or header.get("typ") != "JWT" or header.get("alg") != self._algorithm:
      raise StateResolverError("Invalid header contents")

    signature = JWTStateResolver._b64url_decode(rtoken[(sig_start + 1):])
    actual_signature = hmac.digest(self._secret, rtoken[:sig_start], self._digest)
    if not hmac.compare_digest(signature, actual_signature):
      raise StateResolverError("Invalid JWT signature!")

    payload: Any = json.loads(JWTStateResolver._b64url_decode(parts[1]))
    if not isinstance(payload, dict) or not isinstance(payload.get("exp"), int) or not isinstance(payload.get("data"), dict):
      raise StateResolverError("Invalid JWT payload!")

    timstamp_val = payload["exp"]
    if not isinstance(timstamp_val, int): raise StateResolverError("timestamp is not an int")
    expires_dt = datetime.fromtimestamp(timstamp_val, timezone.utc)
    if expires_dt < datetime.now(tz=timezone.utc):
      raise StateResolverError("JWT expired!")

    try: state_data = StateDataAdapter.validate_python(payload["data"])
    except ValidationError as e: raise StateResolverError(e)
    return state_data

  @staticmethod
  def _b64url_encode(value: bytes | bytearray): return base64.urlsafe_b64encode(value).rstrip(b"=")
  @staticmethod
  def _b64url_decode(value: bytes | bytearray): return base64.urlsafe_b64decode(value + b"=" * (4 - len(value) % 4))

def default_state_resolver() -> JWTStateResolver:
  """
  Creates a JWTStateResolver.
  Uses the environment variable `JWT_SECRET` as its secret, if set, otherwise creates a new random, temporary secret.
  """

  jwt_secret = os.getenv("JWT_SECRET", None)
  if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
  else: jwt_secret = jwt_secret.encode("utf-8")
  return JWTStateResolver(jwt_secret)
