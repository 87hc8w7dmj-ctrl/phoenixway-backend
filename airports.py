"""Airport + airline directory endpoints (autocomplete + lookup)."""

from typing import List

from fastapi import APIRouter

from lib.db import db
from models.travel import AirportOut

router = APIRouter()


def _apt_out(a: dict) -> AirportOut:
    return AirportOut(
        iata=a["iata"],
        name=a["name"],
        city=a["city"],
        city_code=a.get("city_code", a["iata"]),
        country=a.get("country", ""),
        region=a.get("region", ""),
        hub=a.get("hub", False),
    )


@router.get("/airports", response_model=List[AirportOut])
async def list_airports(q: str = "", limit: int = 8):
    """Fuzzy autocomplete on iata/city/country/name. Empty query returns hub airports first."""
    qs = q.strip().lower()
    docs = await db.airports.find().to_list(2000)

    def score(a: dict) -> tuple:
        iata = a["iata"].lower()
        city = a["city"].lower()
        country = a.get("country", "").lower()
        name = a.get("name", "").lower()
        if qs == "":
            return (0 if a.get("hub") else 1, a["iata"])
        if iata == qs:
            key = 0
        elif iata.startswith(qs):
            key = 1
        elif city.startswith(qs):
            key = 2
        elif qs in city:
            key = 3
        elif qs in country or qs in name:
            key = 4
        else:
            key = 99
        return (key, 0 if a.get("hub") else 1, a["iata"])

    docs.sort(key=score)
    return [_apt_out(a) for a in docs[: max(1, min(limit, 25))]]
