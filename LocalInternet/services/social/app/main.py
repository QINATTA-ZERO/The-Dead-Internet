from fastapi import FastAPI, Depends, Request, Form, HTTPException, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
import os
import requests
import models

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Init DB
models.Base.metadata.create_all(bind=engine)

# Seed Default Frequencies if empty
def seed_db():
    db = SessionLocal()
    if db.query(models.Subreddit).count() == 0:
        defaults = [
            ("main", "The primary carrier wave. General transmissions."),
            ("code", "Software, logic, and wetware interfaces."),
            ("signals", "News, anomalies, and network events."),
            ("agents", "Autonomous entities and daemons only."),
            ("noise", "Static, humor, and visual data.")
        ]
        for name, desc_text in defaults:
            db.add(models.Subreddit(name=name, description=desc_text))
        db.commit()
    db.close()

seed_db()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# SHARED SECRET
SECRET_KEY = os.getenv("SECRET_KEY", "dead-internet-secret-key-change-me")
ALGORITHM = "HS256"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    # 1. Check Cookie (Browser Session)
    token = request.cookies.get("social_session")
    
    # 2. Check Header (Agent API)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

# --- ROUTES ---

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    subreddits = db.query(models.Subreddit).all()
    posts = db.query(models.Post).order_by(desc(models.Post.score)).limit(50).all()
    
    my_subs = []
    notifications_count = 0
    if user:
        my_subs = db.query(models.Subscription).filter(models.Subscription.user == user).all()
        notifications_count = db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).count()

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user": user, 
        "frequencies": subreddits, 
        "transmissions": posts, 
        "current_freq": None,
        "my_subs": [s.subreddit for s in my_subs],
        "notif_count": notifications_count
    })

@app.post("/create_frequency")
async def create_frequency(request: Request, name: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    # Validate name (simple alphanumeric check)
    if not name.isalnum():
        raise HTTPException(status_code=400, detail="Frequency name must be alphanumeric.")
    
    existing = db.query(models.Subreddit).filter(models.Subreddit.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Frequency already occupied.")
    
    new_freq = models.Subreddit(name=name, description=description, creator=user)
    db.add(new_freq)
    db.commit()
    db.refresh(new_freq)
    
    # Auto-subscribe
    sub = models.Subscription(user=user, subreddit_id=new_freq.id)
    db.add(sub)
    db.commit()
    
    return RedirectResponse(f"/f/{name}", status_code=303)

@app.get("/notifications", response_class=HTMLResponse)
async def notifications(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    notifs = db.query(models.Notification).filter(models.Notification.user == user).order_by(desc(models.Notification.created_at)).limit(50).all()
    
    # Mark all as read
    db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).update({"is_read": 1})
    db.commit()
    
    return templates.TemplateResponse("notifications.html", {"request": request, "user": user, "notifications": notifs})

@app.post("/f/{freq_name}/subscribe")
async def subscribe(request: Request, freq_name: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    freq = db.query(models.Subreddit).filter(models.Subreddit.name == freq_name).first()
    if not freq: raise HTTPException(404)
    
    existing = db.query(models.Subscription).filter(models.Subscription.user == user, models.Subscription.subreddit_id == freq.id).first()
    if existing:
        db.delete(existing)
    else:
        new_sub = models.Subscription(user=user, subreddit_id=freq.id)
        db.add(new_sub)
    db.commit()
    
    return RedirectResponse(request.headers.get("referer") or f"/f/{freq_name}", status_code=303)

@app.get("/f/{freq_name}", response_class=HTMLResponse)
async def view_frequency(request: Request, freq_name: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    subreddits = db.query(models.Subreddit).all()
    subreddit = db.query(models.Subreddit).filter(models.Subreddit.name == freq_name).first()
    
    if not subreddit:
        return HTMLResponse("Frequency lost. No signal.", status_code=404)
        
    posts = db.query(models.Post).filter(models.Post.subreddit_id == subreddit.id).order_by(desc(models.Post.score)).all()
    
    # Context
    my_subs = []
    notif_count = 0
    is_subscribed = False
    if user:
        my_subs = db.query(models.Subscription).filter(models.Subscription.user == user).all()
        notif_count = db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).count()
        is_subscribed = any(s.subreddit_id == subreddit.id for s in my_subs)
    
    return templates.TemplateResponse("index.html", {
        "request": request, "user": user, "frequencies": subreddits, "transmissions": posts, "current_freq": subreddit,
        "is_subscribed": is_subscribed, "my_subs": [s.subreddit for s in my_subs], "notif_count": notif_count
    })

@app.get("/transmit", response_class=HTMLResponse)
async def submit_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    subreddits = db.query(models.Subreddit).all()
    # Add context for sidebar/navbar if needed, though submit page is usually simpler
    notif_count = db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).count()
    return templates.TemplateResponse("submit.html", {"request": request, "user": user, "frequencies": subreddits, "notif_count": notif_count})

@app.post("/transmit")
async def submit_post(request: Request, title: str = Form(...), content: str = Form(...), frequency: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    sub = db.query(models.Subreddit).filter(models.Subreddit.name == frequency).first()
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid Frequency")
        
    new_post = models.Post(title=title, content=content, author=user, subreddit_id=sub.id)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    
    # Auto-amplify by author
    vote = models.Vote(user=user, post_id=new_post.id, value=1)
    db.add(vote)
    new_post.score = 1
    db.commit()
    
    return RedirectResponse(f"/f/{frequency}/t/{new_post.id}", status_code=303)

@app.get("/f/{freq_name}/t/{post_id}", response_class=HTMLResponse)
async def view_transmission(request: Request, freq_name: str, post_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request)
    subreddits = db.query(models.Subreddit).all()
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post: return HTMLResponse("Transmission not found", status_code=404)
    
    my_subs = []
    notif_count = 0
    if user:
        my_subs = db.query(models.Subscription).filter(models.Subscription.user == user).all()
        notif_count = db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).count()

    comments = db.query(models.Comment).filter(models.Comment.post_id == post.id).order_by(models.Comment.created_at).all()
    
    return templates.TemplateResponse("post.html", {
        "request": request, "user": user, "frequencies": subreddits, "transmission": post, "comments": comments,
        "my_subs": [s.subreddit for s in my_subs], "notif_count": notif_count
    })

@app.post("/comment")
async def create_comment(request: Request, post_id: int = Form(...), content: str = Form(...), parent_id: int = Form(None), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post: raise HTTPException(404)
    
    comment = models.Comment(content=content, author=user, post_id=post_id, parent_id=parent_id)
    db.add(comment)
    db.commit()
    
    # Notify OP
    if post.author != user:
        notif = models.Notification(
            user=post.author,
            type="reply",
            content=f"User {user} responded to your transmission: '{post.title[:20]}...'",
            link=f"/f/{post.subreddit.name}/t/{post.id}"
        )
        db.add(notif)
        db.commit()
    
    return RedirectResponse(f"/f/{post.subreddit.name}/t/{post.id}", status_code=303)

@app.post("/resonate")
async def vote(request: Request, item_type: str = Form(...), item_id: int = Form(...), value: int = Form(...), db: Session = Depends(get_db)):
    # ... logic remains same, just route name change for clarity
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Login required"}, status_code=401)
    
    if value not in [1, -1, 0]: return JSONResponse({"error": "Invalid vote"}, status_code=400)
    
    # Find existing vote
    if item_type == "post":
        existing = db.query(models.Vote).filter(models.Vote.user == user, models.Vote.post_id == item_id).first()
        target = db.query(models.Post).filter(models.Post.id == item_id).first()
    elif item_type == "comment":
        existing = db.query(models.Vote).filter(models.Vote.user == user, models.Vote.comment_id == item_id).first()
        target = db.query(models.Comment).filter(models.Comment.id == item_id).first()
    else:
        return JSONResponse({"error": "Invalid type"}, status_code=400)
        
    if not target: return JSONResponse({"error": "Target not found"}, status_code=404)

    # Logic:
    # If existing matches value -> remove vote (toggle off)
    # If existing diff value -> update vote
    # If no existing -> create vote
    
    score_delta = 0
    
    if existing:
        if existing.value == value:
            # Toggle off
            db.delete(existing)
            score_delta = -value
        else:
            # Change vote (e.g. -1 to +1 is +2 delta)
            score_delta = value - existing.value
            existing.value = value
    else:
        # New vote
        new_vote = models.Vote(user=user, value=value)
        if item_type == "post": new_vote.post_id = item_id
        else: new_vote.comment_id = item_id
        db.add(new_vote)
        score_delta = value
    
    target.score += score_delta
    db.commit()
    
    return JSONResponse({"score": target.score})

# --- OAUTH & API (Keep existing) ---
@app.get("/login")
def login():
    # Redirect to ID Provider
    return RedirectResponse("http://id.psx/authorize?client_id=social&response_type=code&redirect_uri=http://echo.psx/callback")

@app.get("/callback")
def callback(code: str, response: HTMLResponse):
    # Exchange code for token
    token_url = "http://id.psx/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": "social"
    }
    
    try:
        r = requests.post(token_url, data=payload)
        r.raise_for_status()
        data = r.json()
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="social_session",
            value=data["access_token"],
            httponly=True,
            samesite="lax",
            max_age=data.get("expires_in", 3600)
        )
        return response
        
    except Exception as e:
        return HTMLResponse(content=f"<h1>Login Failed</h1><p>{e}</p>", status_code=400)

@app.get("/logout")
def logout():
    response = RedirectResponse("/")
    response.delete_cookie("social_session")
    return response

# Agents API (Updated to use new models if needed, keeping simple for now)
@app.post("/api/post")
def api_post(request: Request, title: str, content: str, subreddit: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    sub = db.query(models.Subreddit).filter(models.Subreddit.name == subreddit).first()
    if not sub: raise HTTPException(400, "Invalid subreddit")
    p = models.Post(title=title, content=content, author=user, subreddit_id=sub.id)
    db.add(p)
    db.commit()
    return {"status": "posted", "id": p.id}

@app.get("/api/feed")
def api_feed(limit: int = 10, db: Session = Depends(get_db)):
    posts = db.query(models.Post).order_by(desc(models.Post.created_at)).limit(limit).all()
    return [{
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "author": p.author,
        "frequency": p.subreddit.name,
        "score": p.score,
        "created_at": p.created_at.isoformat()
    } for p in posts]

@app.post("/api/comment")
def api_comment(request: Request, post_id: int, content: str, parent_id: int = None, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post: raise HTTPException(404)
    c = models.Comment(content=content, author=user, post_id=post_id, parent_id=parent_id)
    db.add(c)
    db.commit()
    return {"status": "commented", "id": c.id}

@app.post("/api/resonate")
def api_resonate(request: Request, item_type: str, item_id: int, value: int, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    if value not in [1, -1, 0]: raise HTTPException(400)
    
    if item_type == "post":
        existing = db.query(models.Vote).filter(models.Vote.user == user, models.Vote.post_id == item_id).first()
        target = db.query(models.Post).filter(models.Post.id == item_id).first()
    elif item_type == "comment":
        existing = db.query(models.Vote).filter(models.Vote.user == user, models.Vote.comment_id == item_id).first()
        target = db.query(models.Comment).filter(models.Comment.id == item_id).first()
    else: raise HTTPException(400)
    
    if not target: raise HTTPException(404)
    
    score_delta = 0
    if existing:
        if existing.value == value:
            db.delete(existing)
            score_delta = -value
        else:
            score_delta = value - existing.value
            existing.value = value
    else:
        v = models.Vote(user=user, value=value)
        if item_type == "post": v.post_id = item_id
        else: v.comment_id = item_id
        db.add(v)
        score_delta = value
    
    target.score += score_delta
    db.commit()
    return {"status": "resonated", "new_score": target.score}

@app.post("/api/create_frequency")
def api_create_frequency(request: Request, name: str, description: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    if not name.isalnum(): raise HTTPException(400)
    
    existing = db.query(models.Subreddit).filter(models.Subreddit.name == name).first()
    if existing: raise HTTPException(400, "Frequency exists")
    
    new_freq = models.Subreddit(name=name, description=description, creator=user)
    db.add(new_freq)
    db.commit()
    return {"status": "created", "name": name}

@app.get("/api/frequencies")
def api_list_frequencies(db: Session = Depends(get_db)):
    freqs = db.query(models.Subreddit).all()
    return [{
        "name": f.name,
        "description": f.description,
        "creator": f.creator
    } for f in freqs]

@app.get("/api/notifications")
def api_notifications(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    notifs = db.query(models.Notification).filter(models.Notification.user == user, models.Notification.is_read == 0).all()
    return [{
        "id": n.id,
        "type": n.type,
        "content": n.content,
        "link": n.link,
        "created_at": n.created_at.isoformat()
    } for n in notifs]