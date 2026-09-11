"""
Order Service — database CRUD for orders.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from loguru import logger
from typing import Optional

from app.models.order import Order


async def get_order(db: AsyncSession, order_id: str, business_id: str) -> Optional[Order]:
    """Look up an order by ID and strictly enforce business_id. Returns None if not found."""
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .where(Order.business_id == business_id)
    )
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession,
    order_id: str,
    business_id: str,
    new_status: str,
    notes: str = "",
) -> Optional[Order]:
    """Update order status and notes. Returns the updated order."""
    order = await get_order(db, order_id, business_id)
    if not order:
        logger.warning(f"Cannot update order {order_id} — not found")
        return None
    order.status = new_status
    order.notes = notes
    order.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(order)
    logger.info(f"Order {order_id} → {new_status}")
    return order


async def revert_order_status(
    db: AsyncSession,
    order_id: str,
    business_id: str,
    original_status: str = "delivered",
) -> Optional[Order]:
    """Revert an order to its original status (used by Undo)."""
    return await update_order_status(db, order_id, business_id, original_status, notes="Reverted by undo action")


async def get_all_orders(db: AsyncSession) -> list[Order]:
    result = await db.execute(select(Order).order_by(Order.created_at.desc()))
    return list(result.scalars().all())


async def find_orders_for_customer(db: AsyncSession, email: Optional[str], name: Optional[str], business_id: str = None) -> list[Order]:
    """
    Smart search for orders matching customer email or customer name.
    Strictly filters by business_id if provided.
    """
    from sqlalchemy import func
    import re

    # 1. Direct match by email (case-insensitive)
    if email:
        email_clean = email.strip().lower()
        stmt = select(Order).where(func.lower(Order.customer_email) == email_clean)
        if business_id:
            stmt = stmt.where(Order.business_id == business_id)
        stmt = stmt.order_by(Order.created_at.desc())
        
        result = await db.execute(stmt)
        orders = list(result.scalars().all())
        if orders:
            return orders

    # 2. Smart match by name (case-insensitive & word overlap)
    if name:
        name_clean = name.strip().lower()
        words = [w for w in re.split(r"\s+", name_clean) if len(w) > 1]

        stmt = select(Order).order_by(Order.created_at.desc())
        if business_id:
            stmt = stmt.where(Order.business_id == business_id)
        result = await db.execute(stmt)
        all_orders = list(result.scalars().all())

        matched = []
        for o in all_orders:
            db_name = (o.customer_name or "").lower()
            db_email = (o.customer_email or "").lower()
            if name_clean == db_name or name_clean in db_name or db_name in name_clean:
                matched.append(o)
            elif words and all(w in db_name or w in db_email for w in words):
                matched.append(o)
            elif words and len(words) > 1 and any(w in db_name for w in words):
                matched.append(o)

        if matched:
            return matched

    return []

