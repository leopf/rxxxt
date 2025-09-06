from abc import abstractmethod
from typing import Callable, Generic, final
from rxxxt.helpers import T

class StateCell:
  @abstractmethod
  def serlialize(self) -> str: pass
  def destroy(self): pass

@final
class StrStateCell(StateCell):
  def __init__(self, value: str) -> None:
    self.value = value

  def serlialize(self): return self.value

class SerilializableStateCell(StateCell, Generic[T]):
  def __init__(self, value: T, serializer: Callable[[T], str]) -> None:
    super().__init__()
    self.value = value
    self._serializer = serializer

  def serlialize(self) -> str: return self._serializer(self.value)
