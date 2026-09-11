import sys
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

import asyncio
from datetime import datetime
from app.core.database import AsyncSessionLocal
from app.models.schemas import IncomingEmail
from app.services.pipeline import process_email

async def test():
    async with AsyncSessionLocal() as db:
        email = IncomingEmail(
            id="test-vague-1",
            from_name="AMKAR MRUNAL",
            from_email="mca25.amkar.mrunal@gnims.com",
            subject="Order details",
            body="I want to know where is my order",
            received_at=datetime.utcnow(),
            attachment_base64=None,
            attachment_filename=None,
            source="ui_test"
        )
        res = await process_email(email, db)
        print("--- RESULT ---")
        print("ACTION:", res.action)
        print("ORDER:", res.order)
        print("HTML REPLY (first 300 chars):\n", res.drafted_reply_html[:300])
        print("\nLOGS:")
        for l in res.action_log:
            print("  ", l.step, "|", l.description)

if __name__ == "__main__":
    asyncio.run(test())
