from sqlalchemy import Column, Integer, String, Text, DateTime, PickleType
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Page(Base):
    __tablename__ = "nexus_pages"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    title = Column(String)
    content = Column(Text) # Stripped text content
    embedding = Column(PickleType) # Storing numpy array
    last_indexed = Column(DateTime, default=datetime.utcnow)
