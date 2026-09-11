from sqlalchemy import Column, String, Integer, Text, DateTime
from datetime import datetime
from app.core.database import Base
import uuid

class ClusterRecord(Base):
    __tablename__ = "clusters"

    id = Column(String, primary_key=True, default=lambda: f"CLUSTER-{uuid.uuid4().hex[:8].upper()}")
    business_id = Column(String, default="biz_tech")
    root_cause_summary = Column(String, nullable=False)
    broadcast_draft_html = Column(Text, nullable=False)
    broadcast_draft_text = Column(Text, nullable=False)
    email_ids = Column(Text, nullable=False) # JSON list of email IDs
    status = Column(String, default="pending") # pending | approved | rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
