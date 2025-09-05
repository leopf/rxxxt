
from abc import ABC, abstractmethod
from datetime import datetime
import re
from typing import Any, Callable, Literal
from pydantic import BaseModel, field_serializer, field_validator, model_serializer

class ContextInputEventHandlerOptions(BaseModel):
  debounce: int | None = None
  throttle: int | None = None
  prevent_default: bool = False

class ContextInputEventDescriptor(BaseModel):
  context_id: str
  handler_name: str
  param_map: dict[str, str]
  options: ContextInputEventHandlerOptions

class ContextInputEventDescriptorGenerator(ABC): # NOTE: this is a typing hack
  @property
  @abstractmethod
  def descriptor(self) -> ContextInputEventDescriptor: pass


class EventBase(BaseModel):
  @model_serializer(mode="wrap")
  def serialize_model(self, old_serizalizer: Callable[[Any], Any]): # TODO: fix typing...
    other = old_serizalizer(self)
    event_name = getattr(self, "event", None)
    if event_name is not None: other["event"] = event_name
    return other

class EventRegisterWindowEvent(EventBase):
  event: Literal["event-modify-window"] = "event-modify-window"
  mode: Literal["add"] | Literal["remove"]
  name: str
  descriptor: ContextInputEventDescriptor

class EventRegisterQuerySelectorEvent(EventBase):
  event: Literal["event-modify-query-selector"] = "event-modify-query-selector"
  mode: Literal["add"] | Literal["remove"]
  name: str
  selector: str
  all: bool
  descriptor: ContextInputEventDescriptor

class SetCookieOutputEvent(EventBase):
  event: Literal["set-cookie"] = "set-cookie"
  name: str
  value: str | None = None
  expires: datetime | None = None
  path: str | None = None
  max_age: int | None = None
  secure: bool | None = None
  http_only: bool | None = None
  domain: str | None = None

  @field_validator('name')
  @classmethod
  def validate_name(cls, value: str):
    if not re.match(r'^[^=;, \t\n\r\f\v]+$', value): raise ValueError("Invalid cookie name")
    return value

  @field_validator('value', "domain")
  @classmethod
  def validate_value(cls, value: str | None):
    if value is None: return None
    if not re.match(r'^[^;, \t\n\r\f\v]+$', value): raise ValueError("Invalid value.")
    return value

  @field_validator('path')
  @classmethod
  def validate_path(cls, value: str | None):
    if value is None: return None
    if not re.match(r'^[^\x00-\x20;,\s]+$', value): raise ValueError("Invalid path value")
    return value

  @field_serializer('expires', when_used='json')
  def seriliaze_expires(self, value: datetime | None): return None if value is None else value.isoformat()

  def to_set_cookie_header(self):
    parts: list[str] = [f"{self.name}={self.value}"]
    if self.path is not None: parts.append(f"path={self.path}")
    if self.expires is not None: parts.append(f"expires={self.expires.strftime('%a, %d %b %G %T %Z')}")
    if self.max_age is not None: parts.append(f"max-age={self.max_age}")
    if self.domain is not None: parts.append(f"domain={self.domain}")
    if self.secure: parts.append("secure")
    if self.http_only: parts.append("httponly")
    return ";".join(parts)

class UseWebsocketOutputEvent(EventBase):
  event: Literal["use-websocket"] = "use-websocket"
  websocket: bool

class NavigateOutputEvent(EventBase):
  event: Literal["navigate"] = "navigate"
  location: str

class ContextInputEvent(BaseModel):
  context_id: str
  data: dict[str, int | float | str | bool | None]

InputEvent = ContextInputEvent
OutputEvent = SetCookieOutputEvent | NavigateOutputEvent | UseWebsocketOutputEvent | EventRegisterWindowEvent | EventRegisterQuerySelectorEvent
