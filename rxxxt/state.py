from abc import ABC, abstractmethod
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import os
import secrets
from typing import Awaitable, Literal
from pydantic import TypeAdapter, ValidationError
import hmac

CompressedState = dict[str, str | dict[str, str]]
CompressedStateAdapter = TypeAdapter(CompressedState)

def compress_state(state: dict[str, str]) -> CompressedState:
  prefixed_state: dict[str, dict[str, str]] = {}
  for k, v in state.items():
    sep_idx = k.rfind("!") + 1
    k1 = k[:sep_idx]
    k2 = k[sep_idx:]
    if k1 not in prefixed_state: prefixed_state[k1] = {}
    prefixed_state[k1][k2] = v

  compressed_state: CompressedState = {}
  for prefix, substate in prefixed_state.items():
    if len(substate) == 1:
      for suffix, value in substate.items():
        compressed_state[prefix + suffix] = value
    else:
      compressed_state[prefix] = substate
  return compressed_state

def decompress_state(compressed_state: CompressedState):
  state: dict[str, str] = {}
  for prefix, substate in compressed_state.items():
    if isinstance(substate, str): state[prefix] = substate
    else:
      for suffix, value in substate.items():
        state[prefix + suffix] = value
  return state

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
    payload = { "exp": int((datetime.now(tz=timezone.utc) + self.max_age).timestamp()), "data": compress_state(data) }
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

    try: compressed_state = CompressedStateAdapter.validate_python(payload["data"])
    except ValidationError as e: raise StateResolverError(e)
    return decompress_state(compressed_state)

  @staticmethod
  def b64url_encode(value: bytes | bytearray): return base64.urlsafe_b64encode(value).rstrip(b"=")
  @staticmethod
  def b64url_decode(value: bytes | bytearray): return base64.urlsafe_b64decode(value + b"=" * (4 - len(value) % 4))

def default_state_resolver():
  jwt_secret = os.getenv("JWT_SECRET", None)
  if jwt_secret is None: jwt_secret = secrets.token_bytes(64)
  else: jwt_secret = jwt_secret.encode("utf-8")
  return JWTStateResolver(jwt_secret)
