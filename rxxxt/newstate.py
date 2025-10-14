from abc import ABC, abstractmethod
from typing import Any, Callable, Set
import weakref

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
