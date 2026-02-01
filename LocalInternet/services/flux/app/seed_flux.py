from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os
import sys

# Add app to path
sys.path.append("/app")
import models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)

def seed():
    with Session(engine) as db:
        # Check if Aether merchant exists
        exists = db.query(models.Merchant).filter(models.Merchant.name == "Aether").first()
        if not exists:
            print("Seeding Aether Merchant...")
            m = models.Merchant(name="Aether", user="system", api_key="system-aether-key")
            db.add(m)
            db.commit()
            print("Done.")
        else:
            print("Aether Merchant already exists.")

if __name__ == "__main__":
    seed()
