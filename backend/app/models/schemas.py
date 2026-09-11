"""Pydantic schemas for request / response validation."""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ResolutionAction(str, Enum):
    REFUND = "refund"
    REPLACE = "replace"
    REISSUE_INVOICE = "reissue_invoice"
    ISSUE_CREDIT = "issue_credit"
    REQUEST_INFO = "request_info"
    ANSWER_QUERY = "answer_query"
    ESCALATE = "escalate"


# ── Email input ────────────────────────────────────────────────────────────────
class IncomingEmail(BaseModel):
    id: str
    from_email: str
    from_name: str
    subject: str
    body: str
    received_at: datetime
    source: str = "demo"          # "demo" | "gmail"
    attachment_filename: Optional[str] = None
    attachment_base64: Optional[str] = None   # base64-encoded image/pdf
    business_id: Optional[str] = "biz_tech"  # tenant isolation


# ── OCR output ─────────────────────────────────────────────────────────────────
class ExtractedInvoiceData(BaseModel):
    order_id: Optional[str] = None
    item: Optional[str] = None
    amount: Optional[float] = None
    raw_ocr_text: str = ""
    extraction_confidence: str = "high"   # high | low


# ── Order ──────────────────────────────────────────────────────────────────────
class OrderSchema(BaseModel):
    id: str
    customer_name: str
    customer_email: str
    item: str
    amount: float
    status: str
    created_at: datetime
    notes: str

    class Config:
        from_attributes = True


# ── Action log ────────────────────────────────────────────────────────────────
class ActionLogEntry(BaseModel):
    timestamp: datetime
    step: str           # "ocr" | "match" | "decision" | "action" | "reply"
    description: str    # Plain English
    detail: Optional[str] = None


class ProcessingResult(BaseModel):
    email_id: str
    action: ResolutionAction
    order: Optional[OrderSchema] = None
    extracted: Optional[ExtractedInvoiceData] = None
    reference_id: Optional[str] = None
    drafted_reply_html: str
    drafted_reply_text: str
    action_log: List[ActionLogEntry]
    attachment_paths: List[str] = []
    escalation_reason: Optional[str] = None
    audit_score: Optional[int] = 100
    audit_status: Optional[str] = "PASS"
    escalation_dossier: Optional[dict] = None



# ── Frontend list item ─────────────────────────────────────────────────────────
class EmailListItem(BaseModel):
    id: str
    from_name: str
    from_email: str
    subject: str
    body: str
    received_at: datetime
    source: str
    action: Optional[str] = None
    processed: bool = False
    outcome: Optional[str] = None
    approved: bool = False
