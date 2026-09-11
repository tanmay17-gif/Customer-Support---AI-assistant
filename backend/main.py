"""
CS Assistant — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings
from app.core.database import init_db
from app.api.routes import router


async def _auto_seed():
    """Seed the database with mock orders if it's empty."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.order import Order
        from sqlalchemy import select, func
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(func.count()).select_from(Order))
            count = result.scalar()
            if count == 0:
                logger.info("Database is empty — auto-seeding orders...")
                import sys, pathlib
                sys.path.insert(0, str(pathlib.Path(__file__).parent))
                from scripts.seed_database import seed
                await seed()
                logger.info("Auto-seed complete")
            else:
                logger.info(f"Database has {count} orders — skipping seed")
    except Exception as e:
        logger.warning(f"Auto-seed failed (non-fatal): {e}")


async def _init_rag():
    """Pre-warm the RAG service for both business accounts."""
    try:
        from app.services.rag_service import RAGService
        rag = RAGService.get_instance()
        await rag.initialize_business("biz_tech")
        await rag.initialize_business("biz_apparel")
    except Exception as e:
        logger.warning(f"RAG init failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CS Assistant starting up...")
    await init_db()
    logger.info("Database initialised")
    await _auto_seed()

    import asyncio
    from app.services.polling import start_polling_loop

    # Run RAG init in background so server binds immediately
    rag_task = asyncio.create_task(_init_rag())
    polling_task = asyncio.create_task(start_polling_loop())

    # Start Telegram Admin Bot
    from app.services.telegram_service import start_bot, stop_bot
    telegram_task = asyncio.create_task(start_bot())

    logger.info("CS Assistant ready — http://localhost:8000/docs")
    yield
    logger.info("CS Assistant shutting down")
    polling_task.cancel()
    rag_task.cancel()
    await stop_bot()


app = FastAPI(
    title="CS Assistant API",
    description="AI-powered customer support assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    from app.core.config import PROJECT_ROOT
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm": f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}",
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "project_root": str(PROJECT_ROOT),
    }
