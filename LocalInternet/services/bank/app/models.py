from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, unique=True, index=True)
    balance = Column(Float, default=1000.0) # Initial credits for new users
    last_updated = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, index=True)
    recipient = Column(String, index=True)
    amount = Column(Float)
    note = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
