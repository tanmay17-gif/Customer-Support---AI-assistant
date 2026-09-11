"""
SQLAlchemy async database setup with SQLite.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import os, pathlib

# Resolve DB path relative to the project root (one level above backend/)
_project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent  # CS_Assistant/
_data_dir = _project_root / "data"
_data_dir.mkdir(parents=True, exist_ok=True)
_db_path = _data_dir / "cs_assistant.db"
# Use forward slashes for cross-platform aiosqlite compatibility
_db_url = "sqlite+aiosqlite:///" + str(_db_path).replace("\\", "/")

engine = create_async_engine(_db_url, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup and apply schema updates."""
    from sqlalchemy import text
    from app.models import business           # noqa
    from app.models import order              # noqa
    from app.models import processing_record  # noqa
    from app.models import email              # noqa
    from app.models import evidence_ledger    # noqa
    from app.models import policy_loop        # noqa
    from app.models import cluster            # noqa
    from app.models import telegram_state     # noqa
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQLite migrations for added columns
        try:
            res_o = await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA table_info(orders)")).fetchall())
            cols_o = [r[1] for r in res_o]
            if "business_id" not in cols_o:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN business_id VARCHAR DEFAULT 'biz_tech'"))

            res_e = await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA table_info(emails)")).fetchall())
            cols_e = [r[1] for r in res_e]
            if "business_id" not in cols_e:
                await conn.execute(text("ALTER TABLE emails ADD COLUMN business_id VARCHAR DEFAULT 'biz_tech'"))

            res_p = await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA table_info(processing_records)")).fetchall())
            cols_p = [r[1] for r in res_p]
            if "business_id" not in cols_p:
                await conn.execute(text("ALTER TABLE processing_records ADD COLUMN business_id VARCHAR DEFAULT 'biz_tech'"))
            if "confirmation_id" not in cols_p:
                await conn.execute(text("ALTER TABLE processing_records ADD COLUMN confirmation_id VARCHAR DEFAULT ''"))
        except Exception:
            pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

