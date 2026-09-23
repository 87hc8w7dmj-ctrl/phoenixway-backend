"""Cross-sell catalog + commerce models (v2). TS mirrors live in frontend/src/lib/types.ts."""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class HotelOut(BaseModel):
    id: str
    name: str
    city: str
    city_code: str
    stars: int
    price_per_night: float
    rating: float
    reviews: int
    amenities: List[str]
    free_cancellation: bool
    image: str
    distance_km: float


class CarOut(BaseModel):
    id: str
    model: str
    category: str
    transmission: str
    seats: int
    bags: int
    price_per_day: float
    company: str
    city_code: str


class TransferOut(BaseModel):
    id: str
    kind: str  # shuttle | private | rideshare
    title: str
    provider: str
    vehicle: str
    price: float
    duration_min: int
    rating: float
    city_code: str


class ActivityOut(BaseModel):
    id: str
    title: str
    category: str
    price: float
    duration_h: float
    rating: float
    city_code: str


class InsurancePlanOut(BaseModel):
    id: str
    provider: str
    plan: str
    coverage: List[str]
    price: float
    rating: float


class TravelerIn(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""


class BookingItemIn(BaseModel):
    type: str  # flight | hotel | car | transfer | activity | insurance
    title: str
    detail: str = ""
    date_start: str
    date_end: Optional[str] = None
    price: float
    meta: dict = {}


class BookingItem(BaseModel):
    id: str
    type: str
    title: str
    detail: str = ""
    date_start: str
    date_end: Optional[str] = None
    price: float
    meta: dict = {}


class BookingIn(BaseModel):
    traveler: TravelerIn
    currency: str = "USD"
    items: List[BookingItemIn] = Field(min_length=1)
    promo: Optional[str] = None


class BookingOut(BaseModel):
    id: str
    code: str
    items: List[BookingItem]
    total: float
    discount: float = 0.0
    promo: Optional[str] = None
    currency: str
    status: str
    created_at: str
    traveler_name: str
    traveler_email: str


class AlertIn(BaseModel):
    origin: str
    destination: str
    threshold: float
    push: bool = True


class AlertOut(BaseModel):
    id: str
    origin: str
    destination: str
    threshold: float
    push: bool
    created_at: str
    current_price: float
    triggered: bool
