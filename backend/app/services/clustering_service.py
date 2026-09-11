import json
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.processing_record import ProcessingRecord
from app.models.email import EmailRecord
from app.models.cluster import ClusterRecord
from app.services.llm_service import GeminiLLMService

async def cluster_pending_emails(db: AsyncSession, business_id: str):
    """
    Finds all 'escalate' or 'pending' emails that have not been processed successfully,
    and clusters them by root cause using the LLM.
    """
    logger.info("Running Semantic Clusterer...")
    
    # 1. Fetch eligible emails
    stmt = (
        select(ProcessingRecord, EmailRecord)
        .join(EmailRecord, ProcessingRecord.email_id == EmailRecord.id)
        .where(ProcessingRecord.business_id == business_id)
        .where(ProcessingRecord.status == "pending")
        .where(ProcessingRecord.action == "escalate")
    )
    result = await db.execute(stmt)
    records = result.all()
    
    if len(records) < 2:
        logger.info("Not enough pending escalated emails to cluster.")
        return

    # 2. Prepare payload for LLM
    emails_payload = []
    for proc, email in records:
        emails_payload.append({
            "email_id": email.id,
            "subject": email.subject,
            "body_preview": email.body[:300]
        })

    # 3. Ask LLM to cluster them
    llm = GeminiLLMService.get_instance()
    prompt = f"""You are a Semantic Clustering Engine. Analyze these {len(emails_payload)} customer emails.
Group them if they are describing the EXACT SAME underlying root cause, even if worded differently (e.g. "Payment deducted but no order" and "Money gone, order missing").
Ignore unique, specific, or personal issues (leave them unclustered).
Only create a cluster if 2 or more emails share the exact same root cause.

EMAILS TO CLUSTER:
{json.dumps(emails_payload, indent=2)}

Return ONLY valid JSON:
{{
  "clusters": [
    {{
      "root_cause_summary": "Clear, 1-sentence description of the shared issue",
      "email_ids": ["id1", "id2"],
      "broadcast_draft_paragraph": "A polite, generalized response paragraph addressing this exact issue to all affected customers."
    }}
  ]
}}"""
    
    try:
        response_text = await llm._generate(prompt, response_mime_type="application/json")
        data = llm._parse_json_safe(response_text)
        clusters_found = data.get("clusters", [])
        
        for c in clusters_found:
            email_ids = c.get("email_ids", [])
            if len(email_ids) >= 2:
                # Create a ClusterRecord
                cluster_rec = ClusterRecord(
                    business_id=business_id,
                    root_cause_summary=c.get("root_cause_summary", "Common Issue"),
                    broadcast_draft_html=f"<p>{c.get('broadcast_draft_paragraph', '')}</p>",
                    broadcast_draft_text=c.get('broadcast_draft_paragraph', ''),
                    email_ids=json.dumps(email_ids),
                    status="pending"
                )
                db.add(cluster_rec)
                
                # Update processing records to point to this cluster, or just mark them so they don't get clustered again
                for eid in email_ids:
                    # Mark as clustered
                    proc_stmt = select(ProcessingRecord).where(ProcessingRecord.email_id == eid)
                    p_res = await db.execute(proc_stmt)
                    p_rec = p_res.scalar_one_or_none()
                    if p_rec:
                        p_rec.status = "clustered"
                
                await db.commit()
                logger.info(f"Created cluster with {len(email_ids)} emails: {cluster_rec.root_cause_summary}")

    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        await db.rollback()
