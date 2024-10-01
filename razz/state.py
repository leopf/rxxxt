from dataclasses import dataclass
import sys
from typing import get_type_hints
from pydantic import BaseModel

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
