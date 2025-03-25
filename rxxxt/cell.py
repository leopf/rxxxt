from abc import abstractmethod
from typing import Callable, Generic
from typing_extensions import TypeVar

class StateCell:
  @property
  @abstractmethod
  def svalue(self) -> str: pass
  def destroy(self): pass

class StrStateCell(StateCell):
  def __init__(self, value: str) -> None:
    self.value = value

  @property
  def svalue(self): return self.value

T = TypeVar("T")
class SerilializableStateCell(StateCell, Generic[T]):
  def __init__(self, value: T, serializer: Callable[[T], str]) -> None:
    super().__init__()
    self.value = value
    self._serializer = serializer

  @property
  def svalue(self) -> str: return self._serializer(self.value)
