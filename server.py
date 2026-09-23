import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    yield
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.get("/meta")
async def meta():
    """App metadata: server-anchored today + currency rates, languages and regions."""
    from lib.dates import today_iso
    from lib.prefs import CURRENCIES, LANGUAGES, RATES, REGIONS
    return {
        "today": today_iso(),
        "rates": RATES,
        "currencies": CURRENCIES,
        "languages": LANGUAGES,
        "regions": REGIONS,
    }


# Feature routers — each exports `router`; all land under /api
from routers.auth import router as auth_router
from routers.airports import router as airports_router
from routers.flights import router as flights_router
from routers.stay import router as stay_router
from routers.bookings import router as bookings_router
from routers.alerts import router as alerts_router
from routers.account import router as account_router
from routers.favourites import router as favourites_router

api_router.include_router(auth_router)
api_router.include_router(airports_router)
api_router.include_router(flights_router)
api_router.include_router(stay_router)
api_router.include_router(bookings_router)
api_router.include_router(alerts_router)
api_router.include_router(account_router)
api_router.include_router(favourites_router)

# Include the router in the main app
app.include_router(api_router)

# Credentialed CORS must never pair with a wildcard origin: when CORS_ORIGINS is "*"
# fall back to an explicit regex covering localhost dev and the app's own hosts.
_origins = [o for o in os.environ.get('CORS_ORIGINS', '*').split(',') if o and o != '*']
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_origins,
    allow_origin_regex=None if _origins else r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://[a-z0-9-]+\.(preview\.)?emergentagent\.com",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
