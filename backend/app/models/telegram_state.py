"""
Telegram monitoring state — stores admin monitoring preferences and activity counters.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from datetime import datetime
from app.core.database import Base


class TelegramState(Base):
    __tablename__ = "telegram_state"

    id = Column(Integer, primary_key=True, default=1)
    chat_id = Column(String, nullable=True)          # Admin chat ID
    monitoring_active = Column(Boolean, default=False)
    paused_since = Column(DateTime, nullable=True)    # When STOP was sent

    # Cumulative counters (reset on each START)
    emails_analyzed = Column(Integer, default=0)
    auto_resolved = Column(Integer, default=0)
    common_issues_detected = Column(Integer, default=0)
    common_responses_sent = Column(Integer, default=0)
    individual_resolved = Column(Integer, default=0)
    escalated = Column(Integer, default=0)
    pending_approvals = Column(Integer, default=0)
    invoices_generated = Column(Integer, default=0)
    errors = Column(Integer, default=0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
