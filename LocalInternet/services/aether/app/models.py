from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Domain(Base):
    __tablename__ = "aether_domains"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    domain_name = Column(String, unique=True) # e.g. my-app.psx
    ip_address = Column(String, default="10.5.0.15") # Default to Hosting Node
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

class Deployment(Base):
    __tablename__ = "aether_deployments"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    name = Column(String)
    repo_url = Column(String) # http://forge.psx/user/repo.git
    domain_id = Column(Integer, ForeignKey("aether_domains.id"), nullable=True)
    status = Column(String, default="queued") # queued, building, live, failed
    internal_port = Column(Integer) # Port on the host container
    last_deployed = Column(DateTime, default=datetime.utcnow)
