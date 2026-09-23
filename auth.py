"""Email + password auth. Sessions are httpOnly cookies — never tokens in JSON."""

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from lib.db import db
from lib.deps import get_current_user
from lib.security import (
    SESSION_COOKIE,
    SESSION_TTL_DAYS,
    hash_password,
    make_token,
    verify_password,
)
from models.auth import LoginIn, SignupIn, UserOut
from routers.account import user_out

router = APIRouter()

# --- crude in-process throttle: 10 credential attempts per IP per minute ----
_WINDOW_S = 60
_MAX_ATTEMPTS = 10
_hits: dict[str, deque] = defaultdict(deque)


def _throttle(request: Request) -> None:
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > _WINDOW_S:
        q.popleft()
    if len(q) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts — try again in a minute")
    q.append(now)


def _set_session(response: Response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_token(user_id),
        httponly=True,
        secure=True,  # the app is served over https; keeps the cookie off plaintext hops
        samesite="lax",
        max_age=60 * 60 * 24 * SESSION_TTL_DAYS,
        path="/",
    )


@router.post("/auth/signup", response_model=UserOut)
async def signup(q: SignupIn, request: Request, response: Response):
    _throttle(request)
    email = q.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Could not create that account — try signing in")
    doc = {
        "id": str(uuid.uuid4()),
        "name": q.name.strip(),
        "email": email,
        "password": hash_password(q.password),
        "currency": "USD",
        "language": "en",
        "region": "US",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    _set_session(response, doc["id"])
    return user_out(doc)


@router.post("/auth/login", response_model=UserOut)
async def login(q: LoginIn, request: Request, response: Response):
    _throttle(request)
    user = await db.users.find_one({"email": q.email.lower()})
    if not user or not verify_password(q.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    _set_session(response, user["id"])
    return user_out(user)


class OkOut(BaseModel):
    ok: bool


@router.post("/auth/logout", response_model=OkOut)
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return OkOut(ok=True)


@router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user_out(user)
