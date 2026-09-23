"""Price alerts — per-route thresholds, evaluated against the live fare engine."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from lib.db import db
from lib.deps import get_current_user
from lib.pricing import cheapest, fetch_legs, refs
from models.commerce import AlertIn, AlertOut

router = APIRouter()

HORIZON_DAYS = 14  # alerts track the cheapest fare ~2 weeks out


@router.post("/alerts", response_model=AlertOut)
async def create_alert(q: AlertIn, user: dict = Depends(get_current_user)):
    apts, _ = await refs()
    if q.origin not in apts or q.destination not in apts:
        raise HTTPException(status_code=404, detail="unknown airport code")
    if q.origin == q.destination:
        raise HTTPException(status_code=422, detail="origin and destination must differ")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "origin": q.origin,
        "destination": q.destination,
        "threshold": q.threshold,
        "push": q.push,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.price_alerts.insert_one(doc)
    return await _with_price(doc)


@router.get("/alerts", response_model=List[AlertOut])
async def my_alerts(user: dict = Depends(get_current_user)):
    docs = await db.price_alerts.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)
    return [await _with_price(d) for d in docs]


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    res = await db.price_alerts.delete_one({"id": alert_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}


async def _with_price(doc: dict) -> AlertOut:
    d = (datetime.now(timezone.utc).date() + timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d")
    lf, lt = await fetch_legs(doc["origin"], doc["destination"])
    price = cheapest(lf, lt, doc["destination"], d, "economy") or 0.0
    return AlertOut(
        id=doc["id"],
        origin=doc["origin"],
        destination=doc["destination"],
        threshold=doc["threshold"],
        push=doc.get("push", True),
        created_at=doc["created_at"],
        current_price=price,
        triggered=bool(price and price <= doc["threshold"]),
    )
