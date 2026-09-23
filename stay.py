"""Cross-sell catalog endpoints: hotels, cars, transfers, activities, insurance."""

from typing import List

from fastapi import APIRouter

from lib.db import db
from models.commerce import ActivityOut, CarOut, HotelOut, InsurancePlanOut, TransferOut

router = APIRouter()


async def _city_code(iata: str) -> str:
    apt = await db.airports.find_one({"iata": iata.upper()})
    return apt["city_code"] if apt else iata.upper()


@router.get("/hotels", response_model=List[HotelOut])
async def list_hotels(iata: str):
    code = await _city_code(iata)
    docs = await db.hotels.find({"city_code": code}).sort("price_per_night", 1).to_list(60)
    return [HotelOut(**d) for d in docs]


@router.get("/cars", response_model=List[CarOut])
async def list_cars(iata: str):
    code = await _city_code(iata)
    docs = await db.cars.find({"city_code": code}).sort("price_per_day", 1).to_list(60)
    return [CarOut(**d) for d in docs]


@router.get("/transfers", response_model=List[TransferOut])
async def list_transfers(iata: str):
    code = await _city_code(iata)
    docs = await db.transfers.find({"city_code": code}).sort("price", 1).to_list(60)
    return [TransferOut(**d) for d in docs]


@router.get("/activities", response_model=List[ActivityOut])
async def list_activities(iata: str):
    code = await _city_code(iata)
    docs = await db.activities.find({"city_code": code}).sort("price", 1).to_list(60)
    return [ActivityOut(**d) for d in docs]


@router.get("/insurance", response_model=List[InsurancePlanOut])
async def list_insurance(days: int = 7):
    days = max(1, min(days, 90))
    docs = await db.insurance_plans.find().to_list(20)
    out: List[InsurancePlanOut] = []
    for p in docs:
        price = round(max(9.0, p["per_day"] * days + p["flat"]), 2)
        out.append(
            InsurancePlanOut(
                id=p["id"],
                provider=p["provider"],
                plan=p["plan"],
                coverage=p["coverage"],
                price=price,
                rating=p["rating"],
            )
        )
    return out
