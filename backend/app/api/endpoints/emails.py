"""
Email API endpoints — Phase 6 core API.
"""
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.models.schemas import IncomingEmail, ProcessingResult, EmailListItem
from app.models.processing_record import ProcessingRecord
from app.services.pipeline import process_email
from app.services.order_service import revert_order_status
from sqlalchemy import select

router = APIRouter()

from app.models.email import EmailRecord

# ── GET /emails — list emails ──────────────────────────────────────────────

@router.get("/", response_model=list[EmailListItem])
async def list_emails(db: AsyncSession = Depends(get_db)):
    """Return list of emails from the database with processing status."""
    
    emails = await db.execute(select(EmailRecord))
    emails_data = emails.scalars().all()

    # Check which have been processed
    result = await db.execute(select(ProcessingRecord))
    records = {r.email_id: r for r in result.scalars().all()}

    items = []
    for e in emails_data:
        rec = records.get(e.id)
        
        outcome = None
        approved = False
        if rec:
            approved = (rec.status == "approved")
            
            # Map background status to frontend tabs
            if rec.status == "resolved" or (approved and rec.action != "escalate"):
                outcome = "resolved"
            elif (rec.status == "pending" and rec.action == "escalate") or (approved and rec.action == "escalate"):
                outcome = "escalated"
            # If it's rejected, maybe it stays in escalated or inbox? We'll put it in escalated.
            elif rec.status == "rejected":
                outcome = "escalated"
        
        items.append(EmailListItem(
            id=e.id,
            from_name=e.from_name,
            from_email=e.from_email,
            subject=e.subject,
            body=e.body,
            received_at=e.received_at,
            source=e.source,
            action=rec.action if rec else None,
            processed=rec is not None,
            outcome=outcome,
            approved=approved,
        ))
    return items


# ── GET /emails/{email_id} — get single email detail ────────────────────────

@router.get("/{email_id}")
async def get_email(email_id: str, db: AsyncSession = Depends(get_db)):
    email = await db.get(EmailRecord, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    # Return as dict matching IncomingEmail schema expectations for the frontend
    return {
        "id": email.id,
        "from_name": email.from_name,
        "from_email": email.from_email,
        "subject": email.subject,
        "body": email.body,
        "received_at": email.received_at,
        "source": email.source,
        "attachment_filename": email.attachment_filename,
        "attachment_base64": email.attachment_base64
    }


# ── POST /emails/process — run the full AI pipeline ─────────────────────────

@router.post("/process", response_model=ProcessingResult)
async def process(email: IncomingEmail, db: AsyncSession = Depends(get_db)):
    """Run the full AI pipeline on a single email and store the result."""
    logger.info(f"Processing email: {email.id} — {email.subject}")
    try:
        result = await process_email(email, db)
    except Exception as e:
        logger.error(f"Pipeline error for {email.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    # Persist result to DB
    try:
        existing = await db.get(ProcessingRecord, email.id)
        record_data = result.model_dump_json()
        if existing:
            existing.action = result.action.value
            existing.order_id = result.order.id if result.order else ""
            existing.result_json = record_data
            existing.status = "pending"
        else:
            record = ProcessingRecord(
                email_id=email.id,
                action=result.action.value,
                order_id=result.order.id if result.order else "",
                result_json=record_data,
                status="pending",
            )
            db.add(record)
        await db.commit()
        
        # If it's a live email, create the draft now
        if email.source == "gmail":
            from app.services import gmail_service
            if gmail_service.is_authenticated():
                result_data = json.loads(record_data)
                gmail_service.create_gmail_draft(
                    to_email=email.from_email,
                    subject=email.subject,
                    html_body=result_data.get("drafted_reply_html", ""),
                    message_id=email.id,
                )
    except Exception as e:
        logger.warning(f"Could not persist result: {e}")

    return result


# ── GET /emails/{email_id}/result — get saved AI result ─────────────────────

@router.get("/{email_id}/result", response_model=ProcessingResult)
async def get_email_result(email_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the saved processing result for an email if it exists."""
    record = await db.get(ProcessingRecord, email_id)
    if not record or not record.result_json:
        raise HTTPException(status_code=404, detail="Result not found")
    
    return json.loads(record.result_json)


# ── POST /emails/{email_id}/approve — approve and finalize ───────────────────

@router.post("/{email_id}/approve")
async def approve(email_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a processed email as approved. For Gmail emails, creates a Draft."""
    record = await db.get(ProcessingRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="No processing result found for this email")

    record.status = "approved"
    await db.commit()

    # Try Gmail draft if authenticated
    draft_created = False
    sent = False
    try:
        from app.services import gmail_service
        if gmail_service.is_authenticated():
            result_data = json.loads(record.result_json)
            # Fetch the original email from DB to get the sender's email and subject
            email = await db.get(EmailRecord, email_id)
            if email:
                html_body = result_data.get("drafted_reply_html", "")
                sent = gmail_service.send_email(
                    to_email=email.from_email,
                    subject=email.subject,
                    html_body=html_body,
                    message_id=email_id
                )
    except Exception as e:
        logger.warning(f"Gmail send failed: {e}")

    return {
        "status": "approved",
        "email_id": email_id,
        "gmail_draft_created": draft_created,
        "sent": sent,
        "message": "Reply approved and sent via Gmail." if sent else "Reply approved and logged.",
    }


# ── POST /emails/{email_id}/undo — revert action ────────────────────────────

@router.post("/{email_id}/undo")
async def undo(email_id: str, db: AsyncSession = Depends(get_db)):
    """Undo the executed action — revert order status."""
    record = await db.get(ProcessingRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="No processing result found")

    # Revert order status to delivered (using record's business_id for isolation)
    if record.order_id:
        business_id = getattr(record, "business_id", "biz_tech") or "biz_tech"
        await revert_order_status(db, record.order_id, business_id, "delivered")

    # Remove the processing record so email can be re-processed
    await db.delete(record)
    await db.commit()

    return {"status": "undone", "email_id": email_id, "message": "Action reversed. Order restored to original status."}


# ── GET /cases/{case_id}/verify-chain — verify cryptographic evidence ledger ──

@router.get("/cases/{case_id}/verify-chain")
async def verify_case_chain(case_id: str, db: AsyncSession = Depends(get_db)):
    """Verifies SHA-256 evidence chain integrity for a specific case."""
    from app.services.ledger_service import verify_chain
    return await verify_chain(db, case_id)


# ── Policy Improvement Proposals Endpoints (Phase 4) ─────────────────────────

@router.get("/policy-proposals/list")
async def list_policy_proposals(business_id: str = "biz_tech", db: AsyncSession = Depends(get_db)):
    """List queued policy amendment proposals for a business."""
    from app.models.policy_loop import PolicyProposal
    res = await db.execute(
        select(PolicyProposal)
        .where(PolicyProposal.business_id == business_id)
        .order_by(PolicyProposal.created_at.desc())
    )
    props = res.scalars().all()
    return [
        {
            "id": p.id,
            "business_id": p.business_id,
            "title": p.title,
            "proposed_diff": p.proposed_diff,
            "reasoning": p.reasoning,
            "cited_case_ids": p.cited_case_ids,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        }
        for p in props
    ]


@router.post("/policy-proposals/{proposal_id}/approve")
async def approve_policy_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    """Approve a policy proposal: updates policy document file & re-indexes ChromaDB RAG."""
    from app.services.policy_service import approve_proposal
    res = await approve_proposal(db, proposal_id)
    if not res:
        raise HTTPException(status_code=404, detail="Proposal not found or already processed")
    return {"status": "approved", "proposal_id": proposal_id, "message": "Policy amendment approved and live RAG index re-indexed."}


@router.post("/policy-proposals/{proposal_id}/reject")
async def reject_policy_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    """Reject a policy proposal without updating live policy."""
    from app.services.policy_service import reject_proposal
    res = await reject_proposal(db, proposal_id)
    if not res:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {"status": "rejected", "proposal_id": proposal_id}


# ── POST /cases/{case_id}/override — Human agent override recording ───────────

@router.post("/cases/{case_id}/override")
async def record_override(
    case_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Record human agent override decision on escalated case, triggering Policy Loop if 3+ accumulate."""
    from app.services.policy_service import record_human_override
    business_id = payload.get("business_id", "biz_tech")
    ai_action = payload.get("ai_action", "escalate")
    human_action = payload.get("human_action", "refund")
    reason = payload.get("reason", "Human manager decision override")

    rec = await record_human_override(
        db, business_id=business_id, case_id=case_id,
        ai_action=ai_action, human_action=human_action, reason=reason
    )
    return {"status": "override_logged", "override_id": rec.id, "case_id": case_id}

# ── Clustering Endpoints (Phase 6) ───────────────────────────────────────────

@router.post("/clusters/trigger")
async def trigger_clustering(business_id: str = "biz_tech", db: AsyncSession = Depends(get_db)):
    from app.services.clustering_service import cluster_pending_emails
    await cluster_pending_emails(db, business_id)
    return {"status": "success", "message": "Clustering job completed"}

@router.get("/clusters/list")
async def list_clusters(business_id: str = "biz_tech", db: AsyncSession = Depends(get_db)):
    from app.models.cluster import ClusterRecord
    res = await db.execute(
        select(ClusterRecord)
        .where(ClusterRecord.business_id == business_id)
        .where(ClusterRecord.status == "pending")
    )
    clusters = res.scalars().all()
    return [
        {
            "id": c.id,
            "root_cause_summary": c.root_cause_summary,
            "broadcast_draft_html": c.broadcast_draft_html,
            "email_ids": json.loads(c.email_ids),
            "created_at": c.created_at.isoformat()
        }
        for c in clusters
    ]

@router.post("/clusters/{cluster_id}/approve")
async def approve_cluster(cluster_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.cluster import ClusterRecord
    from app.services import gmail_service
    c = await db.get(ClusterRecord, cluster_id)
    if not c or c.status != "pending":
        raise HTTPException(status_code=404, detail="Cluster not found or already processed")
    
    email_ids = json.loads(c.email_ids)
    c.status = "approved"
    
    # Send broadcast and update emails
    for eid in email_ids:
        prec = await db.get(ProcessingRecord, eid)
        if prec:
            prec.status = "approved"
        
        e = await db.get(EmailRecord, eid)
        if e and gmail_service.is_authenticated():
            try:
                gmail_service.send_email(
                    to_email=e.from_email,
                    subject=e.subject,
                    html_body=c.broadcast_draft_html,
                    message_id=eid
                )
            except Exception as ex:
                logger.warning(f"Gmail send failed for clustered email {eid}: {ex}")
                
    await db.commit()
    
    # Notify Telegram admin
    try:
        from app.services import telegram_service
        await telegram_service.notify_cluster(
            cluster_id=cluster_id,
            root_cause=c.root_cause_summary,
            count=len(email_ids)
        )
    except Exception as tg_err:
        logger.warning(f"Telegram notification for cluster failed: {tg_err}")

    return {"status": "success", "message": f"Broadcast sent to {len(email_ids)} customers."}

