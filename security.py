"""Password hashing + JWT session tokens. SECRET_KEY lives in backend/.env."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

SESSION_COOKIE = "pw_session"
SESSION_TTL_DAYS = 7

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except Exception:
        return False


def make_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    return jwt.encode({"sub": user_id, "exp": exp}, os.environ["SECRET_KEY"], algorithm="HS256")


def read_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
