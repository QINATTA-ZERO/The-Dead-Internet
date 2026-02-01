from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastembed import TextEmbedding
import numpy as np
import models
import os
import asyncio
from contextlib import asynccontextmanager
import spider

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background crawler
    async def crawler_task():
        await asyncio.sleep(10) # Wait for app to load
        while True:
            try:
                print("BACKGROUND: Starting scheduled crawl...")
                await spider.crawl()
                print("BACKGROUND: Crawl complete. Sleeping for 1 hour.")
            except Exception as e:
                print(f"BACKGROUND: Crawler error: {e}")
            await asyncio.sleep(3600) # Every hour
            
    task = asyncio.create_task(crawler_task())
    yield
    task.cancel()

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Init DB
models.Base.metadata.create_all(bind=engine)

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# Load AI Model (Ultra-Lightweight ONNX)
print("Loading Embedding Model...")
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
print("Model Loaded.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def cosine_similarity(a, b):
    # a: (dim,), b: (n, dim)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b, axis=1)
    return np.dot(b, a) / (norm_a * norm_b)

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str, db: Session = Depends(get_db)):
    if not q: return templates.TemplateResponse("index.html", {"request": request})
    
    # Semantic Search
    query_embedding = list(model.embed([q]))[0]
    
    # Fetch all pages
    pages = db.query(models.Page).all()
    
    results = []
    if pages:
        # Filter out pages with no embedding
        valid_pages = [p for p in pages if p.embedding is not None]
        
        if valid_pages:
            embeddings = np.stack([p.embedding for p in valid_pages])
            
            # Compute Cosine Similarity
            scores = cosine_similarity(query_embedding, embeddings)
            
            # Combine scores with pages
            scored_pages = list(zip(valid_pages, scores))
            
            # Sort by score desc
            scored_pages.sort(key=lambda x: x[1], reverse=True)
            
            # Take top 20, filter threshold > 0.4 (Strict relevance)
            results = [p for p, score in scored_pages[:20] if score > 0.4]

    return templates.TemplateResponse("results.html", {"request": request, "q": q, "results": results})

@app.get("/api/search")
async def api_search(q: str, db: Session = Depends(get_db)):
    if not q: return []
    query_embedding = list(model.embed([q]))[0]
    pages = db.query(models.Page).all()
    results = []
    if pages:
        valid_pages = [p for p in pages if p.embedding is not None]
        if valid_pages:
            embeddings = np.stack([p.embedding for p in valid_pages])
            scores = cosine_similarity(query_embedding, embeddings)
            scored_pages = list(zip(valid_pages, scores))
            scored_pages.sort(key=lambda x: x[1], reverse=True)
            results = [{"url": p.url, "title": p.title, "content": p.content[:200], "score": float(score)} 
                       for p, score in scored_pages[:10] if score > 0.3]
    return results

# API for Spider
@app.post("/api/index")
async def api_index(url: str = Form(...), title: str = Form(...), content: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(models.Page).filter(models.Page.url == url).first()
    
    # Compute Embedding
    embedding = list(model.embed([content]))[0]
    
    if existing:
        existing.title = title
        existing.content = content
        existing.embedding = embedding
        existing.last_indexed = models.datetime.utcnow()
    else:
        new_page = models.Page(url=url, title=title, content=content, embedding=embedding)
        db.add(new_page)
    db.commit()
    return {"status": "indexed"}
