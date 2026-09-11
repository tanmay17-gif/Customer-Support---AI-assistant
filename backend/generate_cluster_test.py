import asyncio
import uuid
from datetime import datetime
import json
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.models.email import EmailRecord
from app.models.processing_record import ProcessingRecord
from sqlalchemy.ext.asyncio import AsyncSession

async def generate_test_cluster_data():
    async with AsyncSessionLocal() as db:
        logger.info("Generating 5 synthetic emails for broadcast testing...")
        
        for i in range(5):
            email_id = f"TEST-CLUSTER-{uuid.uuid4().hex[:6]}"
            
            # Create EmailRecord
            email = EmailRecord(
                id=email_id,
                business_id="biz_tech",
                from_name=f"Test Customer {i+1}",
                from_email=f"customer{i+1}@example.com",
                subject="Billing portal down",
                body=f"Hi, I am getting an Error 500 when I try to access the billing portal. Please fix this.",
                source="test_script",
                received_at=datetime.utcnow(),
            )
            db.add(email)
            
            # Create ProcessingRecord (escalated and pending)
            dummy_dossier = {
                "sentiment": "Frustrated",
                "primary_reason": "Mass outage reported on billing portal.",
                "recommended_action_description": "Investigate and broadcast outage notice."
            }
            
            rec_data = {
                "email_id": email_id,
                "action": "escalate",
                "escalation_reason": "Mass outage reported on billing portal.",
                "escalation_dossier": dummy_dossier
            }
            
            proc = ProcessingRecord(
                email_id=email_id,
                action="escalate",
                status="pending",
                order_id="",
                result_json=json.dumps(rec_data)
            )
            db.add(proc)
            
        await db.commit()
        logger.info("✅ Inserted 5 pending escalations with identical root cause.")

if __name__ == "__main__":
    asyncio.run(generate_test_cluster_data())
