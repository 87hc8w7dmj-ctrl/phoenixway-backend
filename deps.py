"""FastAPI dependencies for the session cookie."""

from typing import Optional

from fastapi import HTTPException, Request

from lib.db import db
from lib.security import SESSION_COOKIE, read_token


def _bearer(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE)


async def get_current_user(request: Request) -> dict:
    token = _bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    user_id = read_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired — sign in again")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


async def optional_user(request: Request) -> Optional[dict]:
    """Same as get_current_user but returns None instead of 401 (public endpoints that personalise)."""
    token = _bearer(request)
    if not token:
        return None
    user_id = read_token(token)
    if not user_id:
        return None
    return await db.users.find_one({"id": user_id})
