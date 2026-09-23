"""Account settings — currency, interface language and region preferences."""

from fastapi import APIRouter, Depends, HTTPException

from lib.db import db
from lib.deps import get_current_user
from lib.prefs import CURRENCIES, LANGUAGES, REGIONS
from models.auth import SettingsIn, UserOut

router = APIRouter()


def user_out(u: dict) -> UserOut:
    return UserOut(
        id=u["id"],
        name=u["name"],
        email=u["email"],
        currency=u.get("currency", "USD"),
        language=u.get("language", "en"),
        region=u.get("region", "US"),
    )


@router.put("/settings", response_model=UserOut)
async def update_settings(q: SettingsIn, user: dict = Depends(get_current_user)):
    patch: dict = {}
    if q.currency is not None:
        if q.currency not in CURRENCIES:
            raise HTTPException(status_code=422, detail="Unsupported currency")
        patch["currency"] = q.currency
    if q.language is not None:
        if q.language not in LANGUAGES:
            raise HTTPException(status_code=422, detail="Unsupported language")
        patch["language"] = q.language
    if q.region is not None:
        if q.region not in REGIONS:
            raise HTTPException(status_code=422, detail="Unsupported region")
        patch["region"] = q.region
    if not patch:
        raise HTTPException(status_code=422, detail="Nothing to update")
    await db.users.update_one({"id": user["id"]}, {"$set": patch})
    user.update(patch)
    return user_out(user)
