from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Email(Base):
    __tablename__ = "emails"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, index=True)
    recipient = Column(String, index=True)
    subject = Column(String)
    body = Column(Text)
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_snoozed = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
