from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
from pydantic import BaseModel
from typing import Optional
import os
import requests
import models
import asyncio
import random
from contextlib import asynccontextmanager

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

async def paycheck_simulator():
    while True:
        await asyncio.sleep(43200) # Every 12 hours
        db = SessionLocal()
        try:
            # Simulated paycheck for all existing wallets
            wallets = db.query(models.Wallet).all()
            for w in wallets:
                amount = random.randint(15, 50)
                w.balance += amount
                tx = models.Transaction(sender="SYSTEM", recipient=w.user, amount=amount, note="Periodic VOX Paycheck")
                db.add(tx)
            db.commit()
            print(f"Simulated paychecks for {len(wallets)} wallets.")
        except Exception as e:
            print(f"Paycheck error: {e}")
        finally:
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background task for paychecks
    task = asyncio.create_task(paycheck_simulator())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", "dead-internet-secret-key-change-me")
ALGORITHM = "HS256"

class PaymentCreate(BaseModel):
    recipient: str
    amount: float
    note: Optional[str] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    token = request.cookies.get("bank_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token: return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError: return None

def get_or_create_wallet(db: Session, user: str):
    wallet = db.query(models.Wallet).filter(models.Wallet.user == user).first()
    if not wallet:
        wallet = models.Wallet(user=user, balance=1000.0) # Starter credits
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return templates.TemplateResponse("landing.html", {"request": request})
    
    wallet = get_or_create_wallet(db, user)
    transactions = db.query(models.Transaction).filter(
        (models.Transaction.sender == user) | (models.Transaction.recipient == user)
    ).order_by(desc(models.Transaction.timestamp)).limit(20).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": user, 
        "wallet": wallet,
        "transactions": transactions
    })

@app.post("/transfer")
async def transfer(request: Request, recipient: str = Form(...), amount: float = Form(...), note: str = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    if amount <= 0: raise HTTPException(400, "Invalid amount")
    
    sender_wallet = get_or_create_wallet(db, user)
    if sender_wallet.balance < amount:
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "user": user, "wallet": sender_wallet, 
            "error": "Insufficient credits for transmission.",
            "transactions": [] 
        })

    recipient_wallet = get_or_create_wallet(db, recipient)
    sender_wallet.balance -= amount
    recipient_wallet.balance += amount
    
    tx = models.Transaction(sender=user, recipient=recipient, amount=amount, note=note)
    db.add(tx)
    db.commit()
    
    return RedirectResponse(url="/?success=1", status_code=303)

# Auth
@app.get("/login")
def login():
    return RedirectResponse("http://id.psx/authorize?client_id=bank&response_type=code&redirect_uri=http://bank.psx/callback")

@app.get("/callback")
def callback(code: str):
    token_url = "http://id.psx/token"
    r = requests.post(token_url, data={"grant_type": "authorization_code", "code": code, "client_id": "bank"})
    r.raise_for_status()
    data = r.json()
    response = RedirectResponse(url="/")
    response.set_cookie(key="bank_session", value=data["access_token"], httponly=True, samesite="lax")
    return response

@app.get("/logout")
def logout():
    res = RedirectResponse("/")
    res.delete_cookie("bank_session")
    return res

# API for Agents
@app.get("/api/balance")
def api_balance(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    wallet = get_or_create_wallet(db, user)
    return {"user": user, "balance": wallet.balance}

@app.post("/api/pay")
def api_pay(data: PaymentCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    
    sender_wallet = get_or_create_wallet(db, user)
    if sender_wallet.balance < data.amount:
        raise HTTPException(400, "Insufficient funds")
        
    recipient_wallet = get_or_create_wallet(db, data.recipient)
    sender_wallet.balance -= data.amount
    recipient_wallet.balance += data.amount
    
    tx = models.Transaction(sender=user, recipient=data.recipient, amount=data.amount, note=data.note)
    db.add(tx)
    db.commit()
    return {"status": "success", "tx_id": tx.id}
