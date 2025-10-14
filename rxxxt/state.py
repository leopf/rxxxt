import os, secrets, weakref
from abc import ABC, abstractmethod
from datetime import timedelta
from collections.abc import Awaitable
from pydantic import TypeAdapter, ValidationError
from rxxxt.helpers import JWTError, JWTManager
from typing import Any, Callable, Set

class StateProducer(ABC):
  @abstractmethod
  def produce(self, key: str) -> str: pass

class StateConsumer(ABC):
  @abstractmethod
  def consume(self, key: str, producer: Callable[[], str]) -> Any: pass
  def detach(self, key: str) -> Any: pass

class StateCell(StateConsumer, StateProducer):
  pass

class KeyState:
  def __init__(self, key: str, value: str | None) -> None:
    self.key: str = key
    self.value: str | None = value
    self.producer: StateProducer | None = None
    self.consumers: weakref.WeakSet[StateConsumer] = weakref.WeakSet()

  @property
  def has_value(self):
    return self.value is not None or self.producer is not None

  def get(self) -> str:
    if self.producer is not None:
      self.value = self.producer.produce(self.key)
      self.producer = None
    if self.value is None:
      raise ValueError("key value is None!")
    return self.value

  def set(self, value: str | StateProducer):
    if isinstance(value, str):
      self.value = value
      self.producer = None
    else:
      self.producer = value

    for consumer in self.consumers:
      if consumer is not self.producer:
        consumer.consume(self.key, self.get)

  def add_consumer(self, consumer: StateConsumer):
    self.consumers.add(consumer)

  def remove_consumer(self, consumer: StateConsumer):
    try:
      self.consumers.remove(consumer)
      consumer.detach(self.key)
    except KeyError: pass

  def destroy(self):
    for consumer in self.consumers:
      consumer.detach(self.key)
    self.consumers.clear()
    self.producer = None
    self.value = None

class State:
  def __init__(self) -> None:
    self._key_states: dict[str, KeyState] = {}

  @property
  def keys(self): return set(self._key_states.keys())

  def get(self, key: str):
    if (state := self._key_states.get(key)) is None:
      state = KeyState(key, None)
      self._key_states[key] = state
    return state

  def set_many(self, kvs: dict[str, str]):
    for k, v in kvs.items(): self.get(k).set(v)

  def delete(self, key: str):
    state = self._key_states.pop(key, None)
    if state is not None:
      state.destroy()

  def get_key_values(self, inactive_prefixes: Set[str]):
    active_keys = self._get_active_keys(inactive_prefixes)
    return { key: state.get() for key, state in self._key_states.items() if key in active_keys and state.has_value }

  def cleanup(self, inactive_prefixes: Set[str]):
    active_keys = self._get_active_keys(inactive_prefixes)
    inactive_keys = tuple(key for key in self._key_states.keys() if key not in active_keys)
    for key in inactive_keys:
      return self.delete(key)

  def destroy(self):
    for state in self._key_states.values():
      state.destroy()
    self._key_states.clear()

  def _get_active_keys(self, inactive_prefixes: Set[str]):
    return set(k for k, v in self._key_states.items() if len(k) == 0 or k[0] not in inactive_prefixes or len(v.consumers) > 0)


class StateResolverError(BaseException): pass

class StateResolver(ABC):
  @abstractmethod
  def create_token(self, data: dict[str, str], old_token: str | None) -> str | Awaitable[str]: pass
  @abstractmethod
  def resolve(self, token: str) -> dict[str, str] | Awaitable[dict[str, str]]: pass

class JWTStateResolver(StateResolver):
  StateDataAdapter = TypeAdapter(dict[str, str])

  def __init__(self, secret: bytes, max_age: timedelta | None = None, algorithm: str = "HS512") -> None:
    super().__init__()
    self._jwt_manager = JWTManager(secret, timedelta(days=1) if max_age is None else max_age, algorithm)

  def create_token(self, data: dict[str, str], old_token: str | None) -> str:
    try: return self._jwt_manager.sign({ "d": data })
    except JWTError as e: raise StateResolverError(e)

  def resolve(self, token: str) -> dict[str, str]:
    try:
      payload = self._jwt_manager.verify(token)
      return JWTStateResolver.StateDataAdapter.validate_python(payload["d"])
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
