from abc import abstractmethod

class StateCell:
  @property
  @abstractmethod
  def svalue(self) -> str: pass
  def destroy(self): pass
