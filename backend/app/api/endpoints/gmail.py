"""Gmail OAuth2 endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter()





@router.get("/status")
async def gmail_status():
    """Check if Gmail is authenticated."""
    try:
        from app.services.gmail_service import is_authenticated, get_authenticated_email
        auth = is_authenticated()
        email = get_authenticated_email() if auth else None
        return {"authenticated": auth, "email": email}
    except Exception:
        return {"authenticated": False, "email": None}

@router.post("/poll")
async def trigger_poll():
    """Manually trigger a Gmail poll iteration."""
    from app.services.polling import trigger_manual_poll
    await trigger_manual_poll()
    return {"status": "ok", "message": "Manual poll triggered"}


@router.get("/emails")
async def get_gmail_emails(max_results: int = 10):
    """Fetch unread emails from Gmail (authenticated only)."""
    try:
        from app.services.gmail_service import fetch_unread_emails, is_authenticated
        if not is_authenticated():
            raise HTTPException(status_code=401, detail="Gmail not authenticated")
        emails = fetch_unread_emails(max_results=max_results)
        return {"emails": emails, "count": len(emails), "source": "gmail"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Gmail emails: {e}")
