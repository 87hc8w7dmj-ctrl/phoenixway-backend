"""Flight metasearch models (v2). TS mirrors live in frontend/src/lib/types.ts."""

from typing import List, Optional

from pydantic import BaseModel, Field


class AirportOut(BaseModel):
    iata: str
    name: str
    city: str
    city_code: str
    country: str
    region: str
    hub: bool


class AirlineOut(BaseModel):
    code: str
    name: str
    alliance: str


class LegOut(BaseModel):
    id: str
    airline: str
    airline_name: str
    alliance: str
    from_iata: str
    from_city: str
    to_iata: str
    to_city: str
    depart: str  # ISO with UTC offset
    arrive: str
    duration_min: int
    aircraft: str


class BaggageOption(BaseModel):
    tier: str  # personal | cabin | checked
    label: str
    delta: float


class ItineraryOut(BaseModel):
    id: str
    legs: List[LegOut]
    price: float
    duration_min: int
    stops: int
    combined: bool
    guaranteed: bool
    warning: Optional[str] = None
    provider: str
    baggage: List[BaggageOption]


class SearchIn(BaseModel):
    origin: str
    destination: str
    date: str
    return_date: Optional[str] = None
    cabin: str = "economy"
    adults: int = Field(1, ge=1, le=9)
    children: int = Field(0, ge=0, le=8)
    infants: int = Field(0, ge=0, le=6)


class SearchOut(BaseModel):
    origin: str
    destination: str
    date: str
    return_date: Optional[str]
    outbound: List[ItineraryOut]
    inbound: List[ItineraryOut]


class NomadStopIn(BaseModel):
    iata: str
    date: str  # departure date FROM this stop


class NomadIn(BaseModel):
    stops: List[NomadStopIn] = Field(min_length=2, max_length=6)
    cabin: str = "economy"


class NomadSegment(BaseModel):
    from_iata: str
    from_city: str
    to_iata: str
    to_city: str
    date: str
    options: List[ItineraryOut]


class NomadAlternate(BaseModel):
    label: str
    segments: List[NomadSegment]
    total: float
    savings: float


class NomadOut(BaseModel):
    segments: List[NomadSegment]
    total: float
    total_duration_min: int
    alternates: List[NomadAlternate]


class CalendarPoint(BaseModel):
    date: str
    price: float


class TrendOut(BaseModel):
    points: List[CalendarPoint]
    verdict: str
    expected_change: float
    best_date: Optional[str] = None


class DropOut(BaseModel):
    origin: str
    origin_city: str
    destination: str
    dest_city: str
    price_now: float
    price_was: float
    percent: float
    date: str


class PopularRoute(BaseModel):
    origin: str
    origin_city: str
    destination: str
    dest_city: str
    price: float


class NearbySuggestion(BaseModel):
    iata: str
    name: str
    city: str
    kind: str  # origin | destination
    price: float
    base_price: float
    save: float
