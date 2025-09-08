from abc import ABC, abstractmethod
from datetime import timedelta
import inspect
import os
import secrets
from typing import Callable, Generic, get_origin, Any
from collections.abc import Awaitable
from pydantic import TypeAdapter, ValidationError

from rxxxt.cell import SerilializableStateCell
from rxxxt.component import Component
from rxxxt.execution import Context, State
from rxxxt.helpers import T, JWTError, JWTManager

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
    self._jwt_manager = JWTManager(secret, timedelta(days=1) if max_age is None else max_age, algorithm)

  def create_token(self, data: dict[str, str], old_token: str | None) -> str:
    try: return self._jwt_manager.sign({ "d": data })
    except JWTError as e: raise StateResolverError(e)

  def resolve(self, token: str) -> dict[str, str]:
    try:
      payload = self._jwt_manager.verify(token)
      return StateDataAdapter.validate_python(payload["d"])
    except (ValidationError, JWTError) as e: raise StateResolverError(e)

def default_state_resolver() -> JWTStateResolver:
  """
  Creates a JWTStateResolver.
  Uses the environment variable `JWT_SECRET` as its secret, if set, otherwise creates a new random, temporary secret.
  """

  jwt_secret = os.getenv("JWT_SECRET", None)
  if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
  else: jwt_secret = jwt_secret.encode("utf-8")
  return JWTStateResolver(jwt_secret)
