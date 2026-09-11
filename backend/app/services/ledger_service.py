"""
Ledger Service — cryptographically appends and verifies SHA-256 evidence chain events.
"""
import hashlib
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.evidence_ledger import EvidenceLedgerEntry


async def append_event(
    db: AsyncSession,
    business_id: str,
    case_id: str,
    event_type: str,
    payload: dict,
) -> EvidenceLedgerEntry:
    """Appends an event to the case's immutable SHA-256 hash chain."""
    # Find last entry for this case
    res = await db.execute(
        select(EvidenceLedgerEntry)
        .where(EvidenceLedgerEntry.case_id == case_id)
        .order_by(EvidenceLedgerEntry.sequence.desc())
        .limit(1)
    )
    last_entry = res.scalar_one_or_none()

    if last_entry:
        sequence = last_entry.sequence + 1
        prev_hash = last_entry.current_hash
    else:
        sequence = 1
        prev_hash = "GENESIS_0000000000000000000000000000000000000000000000000000000000000000"

    timestamp = datetime.utcnow()
    timestamp_str = timestamp.isoformat()
    payload_str = json.dumps(payload, sort_keys=True, default=str)

    raw_data = f"{prev_hash}|{sequence}|{event_type}|{timestamp_str}|{payload_str}"
    current_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    entry = EvidenceLedgerEntry(
        business_id=business_id,
        case_id=case_id,
        sequence=sequence,
        event_type=event_type,
        payload_json=payload_str,
        timestamp=timestamp,
        prev_hash=prev_hash,
        current_hash=current_hash,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info(f"Ledger: Case {case_id} [Seq #{sequence}] {event_type} -> Hash {current_hash[:12]}...")
    return entry


async def verify_chain(db: AsyncSession, case_id: str) -> dict:
    """Recomputes SHA-256 hashes sequentially to verify case evidence chain integrity."""
    res = await db.execute(
        select(EvidenceLedgerEntry)
        .where(EvidenceLedgerEntry.case_id == case_id)
        .order_by(EvidenceLedgerEntry.sequence.asc())
    )
    entries = list(res.scalars().all())

    if not entries:
        return {"is_valid": True, "chain_length": 0, "status": "EMPTY", "entries": []}

    expected_prev_hash = "GENESIS_0000000000000000000000000000000000000000000000000000000000000000"
    
    for entry in entries:
        if entry.prev_hash != expected_prev_hash:
            logger.warning(f"Ledger Tamper Detected on case {case_id} at sequence {entry.sequence}: prev_hash mismatch!")
            return {
                "is_valid": False,
                "chain_length": len(entries),
                "tampered_sequence": entry.sequence,
                "reason": "Previous hash pointer broken",
            }

        timestamp_str = entry.timestamp.isoformat()
        payload_str = entry.payload_json
        raw_data = f"{entry.prev_hash}|{entry.sequence}|{entry.event_type}|{timestamp_str}|{payload_str}"
        recalculated_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

        if recalculated_hash != entry.current_hash:
            logger.warning(f"Ledger Tamper Detected on case {case_id} at sequence {entry.sequence}: current_hash mismatch!")
            return {
                "is_valid": False,
                "chain_length": len(entries),
                "tampered_sequence": entry.sequence,
                "reason": "Entry content payload modified",
            }

        expected_prev_hash = entry.current_hash

    return {
        "is_valid": True,
        "chain_length": len(entries),
        "head_hash": entries[-1].current_hash,
        "entries": [
            {
                "sequence": e.sequence,
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "hash": e.current_hash[:16] + "...",
                "payload": json.loads(e.payload_json) if e.payload_json else {},
            }
            for e in entries
        ],
    }
