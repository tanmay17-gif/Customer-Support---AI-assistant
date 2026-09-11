"""
Policy Loop Models — track human overrides and policy amendment proposals.
"""
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.database import Base


class OverrideRecord(Base):
    __tablename__ = "override_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String, index=True)
    case_id: Mapped[str] = mapped_column(String)
    ai_action: Mapped[str] = mapped_column(String)
    human_action: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    attributes_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PolicyProposal(Base):
    __tablename__ = "policy_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # e.g. prop_biz_tech_101
    business_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    proposed_diff: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    cited_case_ids: Mapped[str] = mapped_column(String)                   # Comma-separated case IDs
    status: Mapped[str] = mapped_column(String, default="pending")        # pending | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
