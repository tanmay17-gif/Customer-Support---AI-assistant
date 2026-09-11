"""
Seed the SQLite database with 20 fake orders.
Run from CS_Assistant root: python backend/scripts/seed_database.py
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import random

# Make sure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ORDERS = [
    ("101", "Tanmay", "www.tanu1725@gmail.com", "Wireless Keyboard", 89.99, "processing"),
    ("102", "Tanmay", "www.tanu1725@gmail.com", "USB Hub", 34.99, "delivered"),
    ("103", "Tanmay", "www.tanu1725@gmail.com", "Laptop Stand", 59.99, "shipped"),
    ("ORD-1001", "Sarah Mitchell", "sarah.mitchell@example.com", "Wireless Keyboard", 89.99, "delivered"),
    ("ORD-1002", "James Okafor", "james.ok@example.com", "USB Hub", 34.99, "delivered"),
    ("ORD-1003", "James Okafor", "james.ok@example.com", "Laptop Stand", 59.99, "delivered"),
    ("ORD-1004", "Raj Patel", "raj.p@example.com", "27-inch Monitor", 449.99, "delivered"),
    ("ORD-1005", "Carlos Rivera", "c.rivera@example.com", "Wireless Mouse", 49.99, "delivered"),
    ("ORD-1006", "David Chen", "d.chen@example.com", "HD Webcam", 79.99, "delivered"),
    ("ORD-1007", "Emily Watson", "emily.w@example.com", "Mechanical Keyboard", 149.99, "shipped"),
    ("ORD-1008", "Tom Harrison", "tom.h@example.com", "Monitor Stand", 89.99, "delivered"),
    ("ORD-1009", "Ananya Patel", "ananya.p@example.com", "USB-C Hub 7-in-1", 45.99, "delivered"),
    ("ORD-1010", "Kevin Nguyen", "k.nguyen@example.com", "Laptop Sleeve 15in", 29.99, "delivered"),
    ("ORD-1011", "Laura Jenkins", "laura.j@example.com", "Pro Drawing Tablet", 299.99, "delivered"),
    ("ORD-1012", "Priya Sharma", "priya.sharma@example.com", "4K Monitor 27in", 649.99, "delivered"),
    ("ORD-1013", "Omar Hassan", "omar.h@example.com", "Cable Management Kit", 19.99, "delivered"),
    ("ORD-1014", "Fatima Al-Rashid", "fatima.ar@example.com", "Laptop Cooler Pad", 39.99, "delivered"),
    ("ORD-1015", "Zoe Campbell", "zoe.c@example.com", "Ergonomic Office Chair", 499.99, "delivered"),
    ("ORD-1016", "Michael Brown", "m.brown@example.com", "Adjustable Desk Lamp", 45.99, "delivered"),
    ("ORD-1017", "Liam Murphy", "liam.m@example.com", "Under-Desk Keyboard Tray", 79.99, "delivered"),
    ("ORD-1018", "Fatima Al-Rashid", "fatima.ar@example.com", "Surge Protector Power Strip", 34.99, "processing"),
    ("ORD-1019", "Sophie Turner", "sophie.t@example.com", "USB-C Docking Station", 189.99, "delivered"),
    ("ORD-1020", "Kevin Nguyen", "k.nguyen@example.com", "External SSD 1TB", 119.99, "delivered"),
]


async def seed():
    from app.core.database import AsyncSessionLocal, init_db
    from app.models.order import Order
    from sqlalchemy import select

    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(Order))
        existing = result.scalars().all()
        if existing:
            print(f"Database already has {len(existing)} orders. Skipping seed.")
            return

        base_date = datetime(2026, 7, 1)
        for i, (oid, name, email, item, amount, status) in enumerate(ORDERS):
            order_date = base_date + timedelta(days=i * 4 + random.randint(0, 3))
            order = Order(
                id=oid,
                customer_name=name,
                customer_email=email,
                item=item,
                amount=amount,
                status=status,
                created_at=order_date,
                updated_at=order_date,
                notes="",
            )
            db.add(order)

        await db.commit()
        print(f"Seeded {len(ORDERS)} orders into the database.")
        for oid, name, _, item, amount, status in ORDERS:
            print(f"  {oid}: {item:35s} ${amount:7.2f}  [{status}]")


if __name__ == "__main__":
    asyncio.run(seed())
