from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
import os
import requests
import models

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", "dead-internet-secret-key-change-me")
ALGORITHM = "HS256"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    token = request.cookies.get("mail_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token: return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError: return None

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def inbox(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return templates.TemplateResponse("landing.html", {"request": request})
    
    emails = db.query(models.Email).filter(
        models.Email.recipient == user,
        models.Email.is_draft == False,
        models.Email.is_snoozed == False
    ).order_by(desc(models.Email.timestamp)).all()
    return templates.TemplateResponse("inbox.html", {"request": request, "user": user, "emails": emails, "folder": "Inbox"})

@app.get("/starred", response_class=HTMLResponse)
async def starred_folder(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    emails = db.query(models.Email).filter(
        models.Email.recipient == user,
        models.Email.is_starred == True
    ).order_by(desc(models.Email.timestamp)).all()
    return templates.TemplateResponse("inbox.html", {"request": request, "user": user, "emails": emails, "folder": "Starred"})

@app.get("/snoozed", response_class=HTMLResponse)
async def snoozed_folder(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    emails = db.query(models.Email).filter(
        models.Email.recipient == user,
        models.Email.is_snoozed == True
    ).order_by(desc(models.Email.timestamp)).all()
    return templates.TemplateResponse("inbox.html", {"request": request, "user": user, "emails": emails, "folder": "Snoozed"})

@app.get("/drafts", response_class=HTMLResponse)
async def drafts_folder(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    emails = db.query(models.Email).filter(
        models.Email.sender == user,
        models.Email.is_draft == True
    ).order_by(desc(models.Email.timestamp)).all()
    return templates.TemplateResponse("inbox.html", {"request": request, "user": user, "emails": emails, "folder": "Drafts"})

@app.get("/sent", response_class=HTMLResponse)
async def sent_folder(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    emails = db.query(models.Email).filter(
        models.Email.sender == user,
        models.Email.is_draft == False
    ).order_by(desc(models.Email.timestamp)).all()
    return templates.TemplateResponse("inbox.html", {"request": request, "user": user, "emails": emails, "folder": "Sent"})

@app.get("/compose", response_class=HTMLResponse)
async def compose_page(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    return templates.TemplateResponse("compose.html", {"request": request, "user": user})

@app.post("/send")
async def send_email(request: Request, recipient: str = Form(...), subject: str = Form(...), body: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    # We should verify recipient exists in ID service in a real app
    new_email = models.Email(sender=user, recipient=recipient, subject=subject, body=body)
    db.add(new_email)
    db.commit()
    return RedirectResponse(url="/sent", status_code=303)

@app.get("/view/{email_id}", response_class=HTMLResponse)
async def view_email(request: Request, email_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    email = db.query(models.Email).filter(models.Email.id == email_id).first()
    if not email or (email.recipient != user and email.sender != user):
        raise HTTPException(403)
    
    if email.recipient == user:
        email.is_read = True
        db.commit()
        
    return templates.TemplateResponse("view.html", {"request": request, "user": user, "email": email})

# Auth
@app.get("/login")
def login():
    return RedirectResponse("http://id.psx/authorize?client_id=mail&response_type=code&redirect_uri=http://mail.psx/callback")

@app.get("/callback")
def callback(code: str):
    token_url = "http://id.psx/token"
    r = requests.post(token_url, data={"grant_type": "authorization_code", "code": code, "client_id": "mail"})
    r.raise_for_status()
    data = r.json()
    response = RedirectResponse(url="/")
    response.set_cookie(key="mail_session", value=data["access_token"], httponly=True, samesite="lax")
    return response

@app.get("/logout")
def logout():
    res = RedirectResponse("/")
    res.delete_cookie("mail_session")
    return res

# API for Agents
@app.post("/api/send")
def api_send(request: Request, recipient: str, subject: str, body: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    new_email = models.Email(sender=user, recipient=recipient, subject=subject, body=body)
    db.add(new_email)
    db.commit()
    return {"status": "sent"}

@app.get("/api/inbox")
def api_inbox(request: Request, limit: int = 20, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    
    emails = db.query(models.Email).filter(
        models.Email.recipient == user,
        models.Email.is_draft == False
    ).order_by(desc(models.Email.timestamp)).limit(limit).all()
    
    return [{
        "id": e.id,
        "sender": e.sender,
        "subject": e.subject,
        "timestamp": e.timestamp.isoformat(),
        "is_read": e.is_read
    } for e in emails]

@app.get("/api/read/{email_id}")
def api_read_email(email_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    
    email = db.query(models.Email).filter(models.Email.id == email_id).first()
    if not email or (email.recipient != user and email.sender != user):
        raise HTTPException(403)
    
    if email.recipient == user:
        email.is_read = True
        db.commit()
        
    return {
        "id": email.id,
        "sender": email.sender,
        "recipient": email.recipient,
        "subject": email.subject,
        "body": email.body,
        "timestamp": email.timestamp.isoformat()
    }
