"""
Policy Service — handles human override tracking, automated policy amendment proposals, and 1-click approvals.
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.policy_loop import OverrideRecord, PolicyProposal
from app.services.llm_service import GeminiLLMService
from app.services.rag_service import RAGService
from app.core.config import settings


async def record_human_override(
    db: AsyncSession,
    business_id: str,
    case_id: str,
    ai_action: str,
    human_action: str,
    reason: str,
    attributes: Optional[dict] = None,
) -> OverrideRecord:
    """Logs a human override when a human agent decisions an escalated case differently from AI."""
    rec = OverrideRecord(
        business_id=business_id,
        case_id=case_id,
        ai_action=ai_action,
        human_action=human_action,
        reason=reason,
        attributes_json=str(attributes or {}),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    logger.info(f"Policy Loop: Human override logged for business '{business_id}' on case '{case_id}' ({ai_action} -> {human_action})")

    # Check cumulative overrides for this business
    res = await db.execute(
        select(func.count())
        .select_from(OverrideRecord)
        .where(OverrideRecord.business_id == business_id)
    )
    count = res.scalar() or 0

    # If 3+ overrides exist and no pending proposal exists, trigger proposal synthesis
    if count >= 3:
        pending_res = await db.execute(
            select(PolicyProposal)
            .where(PolicyProposal.business_id == business_id, PolicyProposal.status == "pending")
        )
        if not pending_res.scalar_one_or_none():
            await generate_proposal_for_business(db, business_id)

    return rec


async def generate_proposal_for_business(db: AsyncSession, business_id: str) -> Optional[PolicyProposal]:
    """Uses LLM to analyze accumulated human overrides and synthesize a policy amendment proposal."""
    res = await db.execute(
        select(OverrideRecord)
        .where(OverrideRecord.business_id == business_id)
        .order_by(OverrideRecord.created_at.desc())
        .limit(10)
    )
    overrides = list(res.scalars().all())
    if not overrides:
        return None

    override_data = [
        {
            "case_id": o.case_id,
            "ai_action": o.ai_action,
            "human_action": o.human_action,
            "reason": o.reason,
        }
        for o in overrides
    ]

    llm = GeminiLLMService.get_instance()
    try:
        proposal_dict = await llm.draft_policy_amendment(business_id, override_data)
        prop_id = f"prop_{business_id}_{uuid.uuid4().hex[:6]}"
        proposal = PolicyProposal(
            id=prop_id,
            business_id=business_id,
            title=proposal_dict.get("title", f"Policy Amendment for {business_id}"),
            proposed_diff=proposal_dict.get("proposed_diff", ""),
            reasoning=proposal_dict.get("reasoning", ""),
            cited_case_ids=", ".join([o.case_id for o in overrides[:3]]),
            status="pending",
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        logger.info(f"Policy Loop: Generated proposal '{prop_id}' for '{business_id}'")
        return proposal
    except Exception as e:
        logger.warning(f"Failed to generate policy proposal: {e}")
        return None


async def approve_proposal(db: AsyncSession, proposal_id: str) -> Optional[PolicyProposal]:
    """Applies human-approved policy amendment to the policy text file and re-indexes ChromaDB."""
    res = await db.execute(select(PolicyProposal).where(PolicyProposal.id == proposal_id))
    proposal = res.scalar_one_or_none()
    if not proposal or proposal.status != "pending":
        return None

    business_id = proposal.business_id
    policy_filename = "stylehub_policy.txt" if business_id == "biz_apparel" else "techgadgets_policy.txt"
    policy_path = Path(settings.POLICY_DOC_PATH).parent / policy_filename

    current_text = policy_path.read_text(encoding="utf-8") if policy_path.exists() else ""
    amended_text = current_text + f"\n\n/* AMENDMENT (Approved {datetime.utcnow().strftime('%Y-%m-%d')} - {proposal.id}) */\n" + proposal.proposed_diff + "\n"

    policy_path.write_text(amended_text, encoding="utf-8")
    proposal.status = "approved"
    await db.commit()

    # Reindex RAG vector database for this business
    rag = RAGService.get_instance()
    await rag.reindex_business_policy(business_id, amended_text)

    logger.info(f"Policy Loop: Proposal '{proposal_id}' APPROVED and live policy updated!")
    return proposal


async def reject_proposal(db: AsyncSession, proposal_id: str) -> Optional[PolicyProposal]:
    """Dismisses a policy proposal without altering live policy."""
    res = await db.execute(select(PolicyProposal).where(PolicyProposal.id == proposal_id))
    proposal = res.scalar_one_or_none()
    if not proposal:
        return None
    proposal.status = "rejected"
    await db.commit()
    return proposal
