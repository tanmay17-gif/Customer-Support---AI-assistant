import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.order import Order

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Order))
        for o in res.scalars().all():
            print(f"{o.id} | {o.customer_name} | {o.customer_email} | {o.item} | ${o.amount} | {o.status}")

if __name__ == "__main__":
    asyncio.run(main())
