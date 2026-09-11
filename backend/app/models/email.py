from sqlalchemy import Column, String
from app.core.database import Base

class EmailRecord(Base):
    __tablename__ = "emails"

    id = Column(String, primary_key=True)
    business_id = Column(String, default="biz_tech")
    from_name = Column(String)
    from_email = Column(String)
    subject = Column(String)
    body = Column(String)
    received_at = Column(String)
    source = Column(String)
    attachment_filename = Column(String, nullable=True)
    attachment_base64 = Column(String, nullable=True)
