"""Deterministic fare engine over the seeded schedule.

Every fare is a pure function of (leg, date, cabin, pax):
    base fare x date-hash multiplier x last-minute urgency x cabin factor x pax load
So calendars, trends and drops are identical across users and reloads, and the
cheap-date heatmaps are meaningful. All datetimes are tz-aware UTC on write.
"""

import hashlib
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException

from lib.db import db
from models.travel import BaggageOption, ItineraryOut, LegOut

CABIN_MULT = {"economy": 1.0, "premium": 1.55, "business": 2.7, "first": 4.4}
PROVIDERS = ["PhoenixWay Direct", "SkyDeal", "TripNest", "AeroHub", "FlyCartel"]
MIN_CONNECT_MIN = 90
GUARANTEE_MIN_CONNECT = 120


def parse_date(s: str) -> date_cls:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"bad date {s!r} — expected YYYY-MM-DD")


def days_ahead(date_iso: str) -> int:
    return (parse_date(date_iso) - datetime.now(timezone.utc).date()).days


def _date_mult(leg_id: str, date_iso: str) -> float:
    h = int(hashlib.md5(f"{leg_id}:{date_iso}".encode()).hexdigest()[:8], 16)
    return 0.75 + (h % 61) / 100.0  # 0.75 .. 1.35


def _sale_mult(leg_id: str, date_iso: str) -> float:
    """Deterministic sales: ~22% of leg-dates carry a 30-45% discount (the 'Drops' feature)."""
    h = int(hashlib.md5(f"sale:{leg_id}:{date_iso}".encode()).hexdigest()[:8], 16) / 16**8
    if h >= 0.22:
        return 1.0
    return 0.55 + (h / 0.22) * 0.15


def _urgency(date_iso: str) -> float:
    d = days_ahead(date_iso)
    if d <= 0:
        return 1.9
    return 1.0 + max(0, 45 - d) * 0.009  # last-minute premium up to ~+40%


def leg_price(leg: dict, date_iso: str, cabin: str, with_sales: bool = True) -> float:
    p = leg["base_price"] * _date_mult(leg["id"], date_iso) * _urgency(date_iso)
    if with_sales:
        p *= _sale_mult(leg["id"], date_iso)
    p *= CABIN_MULT.get(cabin, 1.0)
    return round(p * 1.02, 2)  # taxes + fees


async def refs() -> Tuple[Dict[str, dict], Dict[str, dict]]:
    airports = {a["iata"]: a for a in await db.airports.find().to_list(2000)}
    airlines = {a["code"]: a for a in await db.airlines.find().to_list(500)}
    return airports, airlines


async def fetch_legs(origin: str, dest: str) -> Tuple[List[dict], List[dict]]:
    legs_from = await db.flights.find({"from_iata": origin}).to_list(6000)
    legs_to = await db.flights.find({"to_iata": dest, "from_iata": {"$ne": origin}}).to_list(6000)
    return legs_from, legs_to


def _leg_out(leg: dict, date_iso: str, apts: Dict[str, dict], als: Dict[str, dict]) -> LegOut:
    dep = datetime.strptime(
        f"{date_iso}T{leg['dep_min'] // 60:02d}:{leg['dep_min'] % 60:02d}", "%Y-%m-%dT%H:%M"
    ).replace(tzinfo=timezone.utc)
    arr = dep + timedelta(minutes=leg["dur_min"])
    al = als.get(leg["airline"], {})
    fa, ta = apts.get(leg["from_iata"], {}), apts.get(leg["to_iata"], {})
    return LegOut(
        id=leg["id"],
        airline=leg["airline"],
        airline_name=al.get("name", leg["airline"]),
        alliance=al.get("alliance", "-"),
        from_iata=leg["from_iata"],
        from_city=fa.get("city", leg["from_iata"]),
        to_iata=leg["to_iata"],
        to_city=ta.get("city", leg["to_iata"]),
        depart=dep.isoformat(),
        arrive=arr.isoformat(),
        duration_min=leg["dur_min"],
        aircraft=leg.get("aircraft", "A350-900"),
    )


def _baggage(price: float) -> List[BaggageOption]:
    return [
        BaggageOption(tier="personal", label="Personal item only", delta=0.0),
        BaggageOption(tier="cabin", label="+10 kg cabin bag", delta=round(price * 0.09, 2)),
        BaggageOption(tier="checked", label="+23 kg checked bag", delta=round(price * 0.18, 2)),
    ]


def make_itin(
    pairs: List[Tuple[dict, str]],
    apts: Dict[str, dict],
    als: Dict[str, dict],
    cabin: str,
    pax: float,
) -> ItineraryOut:
    legs = [_leg_out(l, d, apts, als) for l, d in pairs]
    price = round(sum(leg_price(l, d, cabin) for l, d in pairs) * pax, 2)
    t0 = datetime.fromisoformat(legs[0].depart)
    t1 = datetime.fromisoformat(legs[-1].arrive)
    total_min = int((t1 - t0).total_seconds() // 60)
    combined = len(pairs) > 1
    layover = int((datetime.fromisoformat(legs[1].depart) - datetime.fromisoformat(legs[0].arrive)).total_seconds() // 60) if combined else 0
    guaranteed = combined and layover >= GUARANTEE_MIN_CONNECT
    warning = None
    if combined and layover < GUARANTEE_MIN_CONNECT:
        warning = (
            f"Self-transfer in {legs[0].to_city} ({legs[0].to_iata}): re-check baggage and clear "
            f"immigration — not protected by the PhoenixWay Guarantee."
        )
    digest = hashlib.md5("|".join(l["id"] + d for l, d in pairs).encode()).hexdigest()[:10]
    provider = (
        "PhoenixWay Virtual Interlining" if combined else PROVIDERS[int(digest[:4], 16) % len(PROVIDERS)]
    )
    return ItineraryOut(
        id=f"iti-{digest}",
        legs=legs,
        price=price,
        duration_min=total_min,
        stops=len(pairs) - 1,
        combined=combined,
        guaranteed=guaranteed,
        warning=warning,
        provider=provider,
        baggage=_baggage(price),
    )


def compose(
    legs_from: List[dict],
    legs_to: List[dict],
    dest: str,
    date_iso: str,
    cabin: str,
    pax: float,
    apts: Dict[str, dict],
    als: Dict[str, dict],
    limit: int = 20,
) -> List[ItineraryOut]:
    """Direct itineraries + virtual interlining pairs via hub airports (different airlines only)."""
    direct: List[Tuple[dict, str]] = [(l, date_iso) for l in legs_from if l["to_iata"] == dest]
    vi: Dict[str, List[Tuple[float, Tuple[dict, str], Tuple[dict, str]]]] = {}
    for l1 in legs_from:
        hub = l1["to_iata"]
        apt = apts.get(hub)
        if not apt or not apt.get("hub") or hub == dest:
            continue
        arr1 = l1["dep_min"] + l1["dur_min"]
        for l2 in legs_to:
            if l2["from_iata"] != hub or l2["airline"] == l1["airline"]:
                continue
            if l2["dep_min"] < arr1 + MIN_CONNECT_MIN:
                continue
            price = leg_price(l1, date_iso, cabin) + leg_price(l2, date_iso, cabin)
            vi.setdefault(hub, []).append((price, (l1, date_iso), (l2, date_iso)))
    pair_lists: List[List[Tuple[dict, str]]] = [[d] for d in direct]
    for hub_lists in vi.values():
        hub_lists.sort(key=lambda x: x[0])
        for _, p1, p2 in hub_lists[:2]:
            pair_lists.append([p1, p2])
    itins = [make_itin(p, apts, als, cabin, pax) for p in pair_lists]
    itins.sort(key=lambda i: i.price)
    return itins[:limit]


def cheapest(
    legs_from: List[dict],
    legs_to: List[dict],
    dest: str,
    date_iso: str,
    cabin: str = "economy",
    pax: float = 1.0,
    with_sales: bool = True,
) -> Optional[float]:
    """Cheapest direct or virtual-interlining fare for a route on a date (connection window ignored — approximation for aggregations)."""
    best: Optional[float] = None
    for l in legs_from:
        if l["to_iata"] == dest:
            p = leg_price(l, date_iso, cabin, with_sales) * pax
            best = p if best is None or p < best else best
    for l1 in legs_from:
        hub = l1["to_iata"]
        if hub == dest:
            continue
        best2: Optional[float] = None
        for l2 in legs_to:
            if l2["from_iata"] == hub and l2["airline"] != l1["airline"]:
                p2 = leg_price(l2, date_iso, cabin, with_sales)
                best2 = p2 if best2 is None or p2 < best2 else best2
        if best2 is not None:
            p = (leg_price(l1, date_iso, cabin, with_sales) + best2) * pax
            best = p if best is None or p < best else best
    return round(best, 2) if best is not None else None
