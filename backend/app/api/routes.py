"""API router — all endpoints registered here."""
from fastapi import APIRouter
from app.api.endpoints import emails, gmail

router = APIRouter()

router.include_router(emails.router, prefix="/emails", tags=["Emails"])
router.include_router(gmail.router, prefix="/gmail", tags=["Gmail"])


@router.get("/ping")
async def ping():
    return {"message": "pong"}

@router.get("/config")
async def get_config():
    from app.core.config import settings
    return {
        "brand_name": settings.BRAND_NAME,
        "brand_logo_url": settings.BRAND_LOGO_URL
    }
