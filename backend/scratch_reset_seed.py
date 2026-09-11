import sys
import asyncio
from pathlib import Path

sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

from app.core.database import engine
from sqlalchemy import text
from scripts.seed_database import seed

async def reset_and_seed():
    async with engine.begin() as conn:
        await conn.execute(text('DELETE FROM orders'))
    print("Deleted all orders.")
    await seed()

asyncio.run(reset_and_seed())
