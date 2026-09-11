"""
ProcessingRecord — stores the AI pipeline result for each email.
"""
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.database import Base


class ProcessingRecord(Base):
    __tablename__ = "processing_records"

    email_id: Mapped[str]   = mapped_column(String, primary_key=True)
    business_id: Mapped[str] = mapped_column(String, default="biz_tech")
    action: Mapped[str]     = mapped_column(String)              # refund | replace | reissue_invoice | issue_credit | escalate
    order_id: Mapped[str]   = mapped_column(String, default="")
    result_json: Mapped[str]= mapped_column(Text)                # Full ProcessingResult as JSON string
    status: Mapped[str]     = mapped_column(String, default="pending")  # pending | pending_confirmation | resolved | escalated | approved | undone
    confirmation_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
