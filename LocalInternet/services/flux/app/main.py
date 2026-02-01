from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
from pydantic import BaseModel
import os
import requests
import uuid
import models
import seed_flux

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

# Seed
seed_flux.seed()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", "dead-internet-secret-key-change-me")
ALGORITHM = "HS256"

class CheckoutCreate(BaseModel):
    amount: float
    success_url: str
    cancel_url: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    token = request.cookies.get("flux_session")
    if not token: return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError: return None

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def merchant_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return templates.TemplateResponse("landing.html", {"request": request})
    
    merchants = db.query(models.Merchant).filter(models.Merchant.user == user).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "merchants": merchants, "active_tab": "home"})

@app.get("/payments", response_class=HTMLResponse)
async def payments_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    merchant_ids = [m.id for m in db.query(models.Merchant).filter(models.Merchant.user == user).all()]
    sessions = db.query(models.CheckoutSession).filter(models.CheckoutSession.merchant_id.in_(merchant_ids)).order_by(models.CheckoutSession.created_at.desc()).all()
    
    return templates.TemplateResponse("payments.html", {"request": request, "user": user, "sessions": sessions, "active_tab": "payments"})

@app.get("/balances", response_class=HTMLResponse)
async def balances_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    merchants = db.query(models.Merchant).filter(models.Merchant.user == user).all()
    total_flux_balance = sum(m.balance for m in merchants)
    
    return templates.TemplateResponse("balances.html", {"request": request, "user": user, "balance": total_flux_balance, "active_tab": "balances"})

@app.post("/payout")
async def payout(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    merchants = db.query(models.Merchant).filter(models.Merchant.user == user).all()
    total_to_pay = sum(m.balance for m in merchants)
    
    if total_to_pay <= 0:
        return RedirectResponse("/balances?error=no_funds", status_code=303)

    # In a real system, Flux would have a master wallet to pay from.
    # Here, we simulate 'payout' by adding to the user's bank balance.
    try:
        # Payout comes from 'system' or Flux's internal pool
        r = requests.post("http://bank.psx/api/pay", json={
            "recipient": user,
            "amount": total_to_pay,
            "note": "Flux Merchant Payout"
        }, headers={"Authorization": f"Bearer {os.getenv('BANK_SYSTEM_TOKEN', 'flux-master-token')}"})
        # Note: We'd need a master token. For simulation, let's assume the bank allows this.
        
        # Reset merchant balances
        for m in merchants:
            m.balance = 0.0
        db.commit()
    except Exception as e:
        return RedirectResponse(f"/balances?error=payout_failed_{str(e)}", status_code=303)
    
    return RedirectResponse("/balances?success=payout_complete", status_code=303)

@app.get("/checkout/{session_id}", response_class=HTMLResponse)
async def view_checkout(request: Request, session_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: 
        return RedirectResponse(f"/login?next=/checkout/{session_id}")
    
    session = db.query(models.CheckoutSession).filter(models.CheckoutSession.id == session_id).first()
    if not session: raise HTTPException(404)
    if session.status != "pending":
        return HTMLResponse("Session already completed or expired.")

    # Get balance from bank
    token = request.cookies.get("flux_session")
    balance = 0
    try:
        r = requests.get("http://bank.psx/api/balance", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        balance = r.json().get("balance", 0)
    except:
        pass

    return templates.TemplateResponse("checkout.html", {
        "request": request, "session": session, "user": user, "balance": balance
    })

@app.post("/checkout/{session_id}/confirm")
async def process_payment(request: Request, session_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse(f"/login?next=/checkout/{session_id}")
    
    session = db.query(models.CheckoutSession).filter(models.CheckoutSession.id == session_id).first()
    if not session or session.status != "pending": raise HTTPException(400)
    
    token = request.cookies.get("flux_session")
    try:
        merchant = db.query(models.Merchant).filter(models.Merchant.id == session.merchant_id).first()
        # User pays Flux (who then holds the money for merchant)
        # For simplicity, user pays the merchant user directly, OR we track it in Flux.
        # User requested 'real' implementation: User pays Merchant, Flux takes a cut (optional), 
        # but Flux usually holds it. Let's make user pay Flux 'system' account, 
        # and Flux increases the merchant's virtual balance.
        
        r = requests.post("http://bank.psx/api/pay", json={
            "recipient": "flux_system", # Flux system account
            "amount": session.amount,
            "note": f"Checkout {session.id}"
        }, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        
        # Increase Merchant Balance
        merchant.balance += session.amount
        session.status = "completed"
        db.commit()
        
    except Exception as e:
        # Re-fetch balance for template
        balance = 0
        try:
            rb = requests.get("http://bank.psx/api/balance", headers={"Authorization": f"Bearer {token}"})
            balance = rb.json().get("balance", 0)
        except: pass
        return templates.TemplateResponse("checkout.html", {
            "request": request, "session": session, "user": user, "balance": balance, "error": f"Bank Transfer Failed: {str(e)}"
        })

    return RedirectResponse(url=session.success_url, status_code=303)

# --- API FOR MERCHANTS ---

@app.post("/api/checkout/create")
def api_create_session(data: CheckoutCreate, request: Request, db: Session = Depends(get_db)):
    api_key = request.headers.get("X-Flux-Key")
    merchant = db.query(models.Merchant).filter(models.Merchant.api_key == api_key).first()
    if not merchant: raise HTTPException(401)
    
    sid = str(uuid.uuid4())
    session = models.CheckoutSession(
        id=sid, merchant_id=merchant.id, amount=data.amount, 
        success_url=data.success_url, cancel_url=data.cancel_url
    )
    db.add(session)
    db.commit()
    
    return {"checkout_url": f"http://flux.psx/checkout/{sid}", "id": sid}

# --- AUTH ---
@app.get("/login")
def login(next: str = "/"):
    return RedirectResponse(f"http://id.psx/authorize?client_id=flux&response_type=code&redirect_uri=http://flux.psx/callback")

@app.get("/callback")
def callback(code: str):
    r = requests.post("http://id.psx/token", data={"grant_type": "authorization_code", "code": code, "client_id": "flux"})
    data = r.json()
    response = RedirectResponse(url="/")
    response.set_cookie(key="flux_session", value=data["access_token"], httponly=True, samesite="lax")
    return response

@app.get("/logout")
def logout():
    res = RedirectResponse("/")
    res.delete_cookie("flux_session")
    return res
