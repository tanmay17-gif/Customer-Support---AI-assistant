import sys
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

import asyncio
from app.core.database import engine
from sqlalchemy import text

async def main():
    try:
        async with engine.begin() as conn:
            res = await conn.execute(text('SELECT * FROM emails LIMIT 1'))
            print("Emails:", res.fetchall())
    except Exception as e:
        print("DB Error:", e)

asyncio.run(main())
