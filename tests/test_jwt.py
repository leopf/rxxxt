import unittest
import jwt
from datetime import datetime, timedelta, timezone
from rxxxt.state import JWTStateResolver, StateResolverError

def encode_own_jwt(payload: dict[str, str], secret: str, max_age: timedelta, algorithm: str):
  r = JWTStateResolver(secret.encode("utf-8"), max_age, algorithm)
  return r.create_token(payload, None)

def decode_own_jwt(token: str, secret: str, max_age: timedelta, algorithm: str):
  r = JWTStateResolver(secret.encode("utf-8"), max_age, algorithm)
  return r.resolve(token)

def encode_ref_jwt(payload: dict[str, str], secret: str, max_age: timedelta, algorithm: str):
  data = { "data": payload, "exp": int((datetime.now(tz=timezone.utc) + max_age).timestamp()) }
  return jwt.encode(data, secret, algorithm)

def decode_ref_jwt(token: str, secret: str, _max_age: timedelta, algorithm: str):
  data = jwt.decode(token, secret, [algorithm])
  return data["data"]

class TestJWT(unittest.TestCase):
  def test_encode(self):
    args = ("12345678", timedelta(days=1), "HS512")

    data = { "Hello": "World" }
    token = encode_own_jwt(data, *args)
    token_data = decode_ref_jwt(token, *args)

    self.assertDictEqual(data, token_data)

  def test_decode(self):
    args = ("12345678", timedelta(days=1), "HS512")

    data = { "Hello": "World" }
    token = encode_ref_jwt(data, *args)
    token_data = decode_own_jwt(token, *args)

    self.assertDictEqual(data, token_data)

  def test_expired(self):
    args = ("12345678", timedelta(days=-1), "HS512")
    token = encode_ref_jwt({ "Hello": "World" }, *args)
    with self.assertRaises(StateResolverError):
      _ = decode_own_jwt(token, *args)

  def test_invalid(self):
    args = (timedelta(days=1), "HS512")
    token = encode_ref_jwt({ "Hello": "World" }, "1234", *args)

    _ = decode_own_jwt(token, "1234", *args)
    with self.assertRaises(StateResolverError):
      _ = decode_own_jwt(token, "1235", *args)

if __name__ == "__main__":
  _ = unittest.main()
