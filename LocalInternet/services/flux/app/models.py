from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    user = Column(String) # Owner
    api_key = Column(String, unique=True)
    balance = Column(Float, default=0.0) # Accumulated revenue ready for payout

class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id = Column(String, primary_key=True) # UUID
    merchant_id = Column(Integer, ForeignKey("merchants.id"))
    amount = Column(Float)
    currency = Column(String, default="VOX")
    status = Column(String, default="pending") # pending, completed, failed
    success_url = Column(String)
    cancel_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
