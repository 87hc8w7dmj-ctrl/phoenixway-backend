"""Favourites — per-user saved flights, synced across devices for signed-in users."""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lib.db import db
from lib.deps import get_current_user
from models.favourites import FavouriteIn, FavouriteOut

router = APIRouter()

MAX_FAVOURITES = 200


class OkOut(BaseModel):
    ok: bool


@router.get("/favourites", response_model=List[FavouriteOut])
async def list_favourites(user: dict = Depends(get_current_user)):
    docs = await db.favourites.find({"user_id": user["id"]}).sort("created_at", -1).to_list(MAX_FAVOURITES)
    return [FavouriteOut(**{k: v for k, v in d.items() if k not in ("_id", "user_id")}) for d in docs]


@router.post("/favourites", response_model=FavouriteOut)
async def add_favourite(q: FavouriteIn, user: dict = Depends(get_current_user)):
    existing = await db.favourites.find_one({"user_id": user["id"], "itinerary_id": q.itinerary_id})
    if existing:
        return FavouriteOut(**{k: v for k, v in existing.items() if k not in ("_id", "user_id")})
    count = await db.favourites.count_documents({"user_id": user["id"]})
    if count >= MAX_FAVOURITES:
        raise HTTPException(status_code=422, detail="Favourites list is full — remove one first")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": None,
        **q.model_dump(),
    }
    await db.favourites.insert_one(doc)
    return FavouriteOut(**{k: v for k, v in doc.items() if k not in ("_id", "user_id")})


@router.delete("/favourites/{fav_id}", response_model=OkOut)
async def delete_favourite(fav_id: str, user: dict = Depends(get_current_user)):
    res = await db.favourites.delete_one({"id": fav_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favourite not found")
    return OkOut(ok=True)
