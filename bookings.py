"""Bookings ("My Trips") — created from the unified checkout, tied to the signed-in user."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from lib.db import db
from lib.deps import get_current_user
from lib.prefs import CURRENCIES
from models.commerce import BookingIn, BookingItem, BookingItemIn, BookingOut

router = APIRouter()

PROMOS = {"PHOENIX10": ("percent", 0.10), "PWGEM50": ("flat", 50.0)}


@router.post("/bookings", response_model=BookingOut)
async def create_booking(q: BookingIn, user: dict = Depends(get_current_user)):
    subtotal = sum(i.price for i in q.items)
    discount = 0.0
    promo = (q.promo or "").strip().upper() or None
    if any(i.price < 0 for i in q.items):
        raise HTTPException(status_code=422, detail="Item prices must be positive")
    if promo:
        rule = PROMOS.get(promo)
        if not rule:
            raise HTTPException(status_code=422, detail="Unknown promo code")
        kind, val = rule
        if promo == "PWGEM50" and subtotal < 200:
            raise HTTPException(status_code=422, detail="PWGEM50 applies to carts of $200+")
        discount = round(subtotal * val, 2) if kind == "percent" else min(val, subtotal)
    total = round(subtotal - discount, 2)
    items = [BookingItem(id=str(uuid.uuid4()), **i.model_dump()) for i in q.items]
    doc = {
        "id": str(uuid.uuid4()),
        "code": "PW-" + uuid.uuid4().hex[:6].upper(),
        "user_id": user["id"],
        "items": [i.model_dump() for i in items],
        "total": total,
        "discount": discount,
        "promo": promo,
        "currency": q.currency if q.currency in CURRENCIES else "USD",
        "status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "traveler_name": q.traveler.name,
        "traveler_email": q.traveler.email,
    }
    await db.bookings.insert_one(doc)
    return BookingOut(**doc)


@router.get("/bookings", response_model=List[BookingOut])
async def my_bookings(user: dict = Depends(get_current_user)):
    docs = await db.bookings.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    return [BookingOut(**d) for d in docs]


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: str, user: dict = Depends(get_current_user)):
    doc = await db.bookings.find_one({"id": booking_id, "user_id": user["id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingOut(**doc)
