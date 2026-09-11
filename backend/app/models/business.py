"""Business model for multi-account support."""
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # e.g. biz_tech, biz_apparel
    name: Mapped[str] = mapped_column(String)                            # e.g. TechGadgets Inc.
    policy_document_path: Mapped[str] = mapped_column(String)            # Path to policy file
    gmail_account: Mapped[str] = mapped_column(String, default="")       # Gmail/IMAP account email
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
