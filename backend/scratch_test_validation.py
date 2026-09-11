import sys
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

import asyncio
from app.core.database import engine
from sqlalchemy import select
from app.models.email import EmailRecord
from app.models.schemas import EmailListItem

async def main():
    try:
        async with engine.begin() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(engine) as db:
                emails = await db.execute(select(EmailRecord))
                emails_data = emails.scalars().all()
                
                for e in emails_data:
                    try:
                        item = EmailListItem(
                            id=e.id,
                            from_name=e.from_name,
                            from_email=e.from_email,
                            subject=e.subject,
                            body=e.body,
                            received_at=e.received_at,
                            source=e.source,
                            action=None,
                            processed=False,
                        )
                        print("Success:", item.id)
                    except Exception as ve:
                        print("ValidationError:", ve)
    except Exception as e:
        print("DB Error:", e)

asyncio.run(main())
