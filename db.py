import os
from motor.motor_asyncio import AsyncClient, AsyncDatabase

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

client: AsyncClient = AsyncClient(MONGO_URL)
db: AsyncDatabase = client.phoenixway


async def ensure_indexes():
    pass
