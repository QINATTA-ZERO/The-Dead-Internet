from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
import os
import requests
import models
import subprocess
import shutil

# DB Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", "dead-internet-secret-key-change-me")
ALGORITHM = "HS256"
FLUX_KEY = os.getenv("FLUX_KEY", "system-aether-key")
HOSTED_SITES_DIR = "/hosted_sites"
ZONE_FILE = "/etc/coredns/db.psx"

def increment_dns_serial():
    if not os.path.exists(ZONE_FILE): return
    try:
        with open(ZONE_FILE, "r") as f:
            lines = f.readlines()
        
        import datetime
        today = datetime.datetime.now().strftime("%Y%m%d")
        
        new_lines = []
        for line in lines:
            if "; Serial" in line:
                parts = line.split(";")
                current_val = parts[0].strip()
                if current_val.startswith(today) and len(current_val) == 10:
                    new_val = str(int(current_val) + 1)
                else:
                    new_val = today + "01"
                new_lines.append(f"            {new_val:<10} ; Serial\n")
            else:
                new_lines.append(line)
                
        with open(ZONE_FILE, "w") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Serial Update Error: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request):
    token = request.cookies.get("aether_session")
    if not token: return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError: return None

@app.get("/docs", response_class=HTMLResponse)
async def documentation(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def aether_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return templates.TemplateResponse("landing.html", {"request": request})
    
    domains = db.query(models.Domain).filter(models.Domain.user == user).all()
    deployments = db.query(models.Deployment).filter(models.Deployment.user == user).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "domains": domains, "deployments": deployments, "active_tab": "dashboard"
    })

@app.get("/domains", response_class=HTMLResponse)
async def domains_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    domains = db.query(models.Domain).filter(models.Domain.user == user).all()
    return templates.TemplateResponse("domains.html", {"request": request, "user": user, "domains": domains, "active_tab": "domains"})

@app.get("/compute", response_class=HTMLResponse)
async def compute_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    # User-specific compute view
    user_deployments = db.query(models.Deployment).filter(models.Deployment.user == user).all()
    
    # Simulated metrics per deployment
    stats = {
        "cpu": len(user_deployments) * 1.5, # 1.5% CPU per site
        "memory": len(user_deployments) * 128, # 128MB per site
        "deployments_active": len([d for d in user_deployments if d.status == 'live']),
        "nodes": 1 # Standard single-node hosting
    }

    return templates.TemplateResponse("compute.html", {
        "request": request, "user": user, "stats": stats, "active_tab": "compute", "deployments": user_deployments
    })

@app.get("/storage", response_class=HTMLResponse)
async def storage_page(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    return templates.TemplateResponse("storage.html", {"request": request, "user": user, "active_tab": "storage"})

@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    # Fetch billing history from flux.psx (we'd need a token or api key)
    # For now, let's just show an empty list or integrated view if possible
    return templates.TemplateResponse("billing.html", {"request": request, "user": user, "active_tab": "billing"})

# --- DOMAIN REGISTRATION ---

@app.post("/domains/purchase")
async def purchase_domain(request: Request, domain: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    if not domain.endswith(".psx"): domain += ".psx"
    
    existing = db.query(models.Domain).filter(models.Domain.domain_name == domain).first()
    if existing: return RedirectResponse(f"/?error=Domain {domain} is already registered.")

    try:
        # Note: Flux expects a JSON body (Pydantic model)
        r = requests.post("http://flux.psx/api/checkout/create", 
            json={"amount": 50.0, "success_url": f"http://aether.psx/domains/confirm?d={domain}", "cancel_url": "http://aether.psx/"},
            headers={"X-Flux-Key": FLUX_KEY},
            timeout=5
        )
        if r.status_code != 200:
            return RedirectResponse(f"/?error=Billing Service Error: {r.text}")
            
        data = r.json()
        checkout_url = data.get("checkout_url")
        if not checkout_url:
            return RedirectResponse(f"/?error=Invalid response from billing service: {data}")
            
        return RedirectResponse(url=checkout_url, status_code=303)
    except Exception as e:
        return RedirectResponse(f"/?error=Billing service unreachable: {str(e)}")

@app.get("/domains/confirm")
async def confirm_domain(d: str, db: Session = Depends(get_db), request: Request = None):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    subdomain = d.replace(".psx", "")
    
    exists = db.query(models.Domain).filter(models.Domain.domain_name == d).first()
    if exists: return RedirectResponse("/?error=already_owned")

    try:
        # 1. Update DNS Zone
        with open(ZONE_FILE, "a") as f:
            f.write(f"{subdomain:<8} IN  A   10.5.0.15\n")
        increment_dns_serial()
            
    except Exception as e:
        print(f"Provisioning Error: {e}")
    
    new_domain = models.Domain(user=user, domain_name=d, ip_address="10.5.0.15")
    db.add(new_domain)
    db.commit()
    
    return RedirectResponse(url="/domains?success=domain_active")

@app.post("/domains/update_ip")
async def update_domain_ip(request: Request, domain_id: int = Form(...), new_ip: str = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    domain = db.query(models.Domain).filter(models.Domain.id == domain_id, models.Domain.user == user).first()
    if not domain: raise HTTPException(404)

    # 1. Update DB
    old_ip = domain.ip_address
    domain.ip_address = new_ip
    db.commit()

    # 2. Update Zone File (Simple replacement)
    subdomain = domain.domain_name.replace(".psx", "")
    
    try:
        with open(ZONE_FILE, "r") as f:
            lines = f.readlines()
        
        with open(ZONE_FILE, "w") as f:
            for line in lines:
                if line.startswith(f"{subdomain:<8}"):
                    f.write(f"{subdomain:<8} IN  A   {new_ip}\n")
                else:
                    f.write(line)
        increment_dns_serial()
    except Exception as e:
        print(f"DNS Rewrite Error: {e}")

    return RedirectResponse(url="/domains?success=ip_updated")

# --- DEPLOYMENTS ---

@app.post("/deploy")
async def deploy_code(request: Request, name: str = Form(...), repo: str = Form(...), domain_id: int = Form(...), db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    domain = db.query(models.Domain).filter(models.Domain.id == domain_id, models.Domain.user == user).first()
    if not domain: raise HTTPException(400, "Invalid domain selection")

    target_dir = os.path.join(HOSTED_SITES_DIR, domain.domain_name)
    
    try:
        # Simple deployment: Clone or pull
        # In a real internet, we'd use ssh keys or token-based git auth.
        # Here we assume repo is accessible via HTTP within the network.
        if os.path.exists(target_dir):
            subprocess.run(["git", "-C", target_dir, "pull"], check=True, capture_output=True)
        else:
            subprocess.run(["git", "clone", repo, target_dir], check=True, capture_output=True)
        
        status = "live"
    except Exception as e:
        print(f"Deployment Error: {e}")
        status = "failed"

    dep = db.query(models.Deployment).filter(models.Deployment.name == name, models.Deployment.user == user).first()
    if dep:
        dep.repo_url = repo
        dep.status = status
        dep.last_deployed = datetime.utcnow()
    else:
        dep = models.Deployment(user=user, name=name, repo_url=repo, domain_id=domain.id, status=status)
        db.add(dep)
    
    db.commit()
    return RedirectResponse(url=f"/?deployed={status}", status_code=303)

# --- AUTH ---
@app.get("/login")
def login():
    return RedirectResponse("http://id.psx/authorize?client_id=aether&response_type=code&redirect_uri=http://aether.psx/callback")

@app.get("/callback")
def callback(code: str):
    r = requests.post("http://id.psx/token", data={"grant_type": "authorization_code", "code": code, "client_id": "aether"})
    data = r.json()
    response = RedirectResponse(url="/")
    response.set_cookie(key="aether_session", value=data["access_token"], httponly=True, samesite="lax")
    return response

@app.get("/logout")
def logout():
    res.delete_cookie("aether_session")
    return res

# --- AGENT API ---

@app.post("/api/domains/purchase")
def api_purchase_domain(request: Request, domain: str, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    
    if not domain.endswith(".psx"): domain += ".psx"
    existing = db.query(models.Domain).filter(models.Domain.domain_name == domain).first()
    if existing: raise HTTPException(400, "Domain taken")

    # For Agents, we bypass the Flux checkout UI and just call the bank directly
    # This assumes Aether is trusted to move VOX for the user
    # Or we require the user to have a valid Flux session (hard for agents)
    # Let's use the bank API directly with the user's token
    auth_header = request.headers.get("Authorization")
    try:
        r = requests.post("http://bank.psx/api/pay", 
            json={"recipient": "aether_admin", "amount": 50.0, "note": f"Purchase {domain}"},
            headers={"Authorization": auth_header},
            timeout=5
        )
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"Payment failed: {str(e)}")

    # Provision
    subdomain = domain.replace(".psx", "")
    with open(ZONE_FILE, "a") as f:
        f.write(f"{subdomain:<8} IN  A   10.5.0.15\n")
    increment_dns_serial()

    new_domain = models.Domain(user=user, domain_name=domain, ip_address="10.5.0.15")
    db.add(new_domain)
    db.commit()
    return {"status": "active", "domain": domain}

@app.post("/api/deploy")
def api_deploy(request: Request, name: str, repo: str, domain_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user: raise HTTPException(401)
    
    domain = db.query(models.Domain).filter(models.Domain.id == domain_id, models.Domain.user == user).first()
    if not domain: raise HTTPException(404)

    target_dir = os.path.join(HOSTED_SITES_DIR, domain.domain_name)
    try:
        if os.path.exists(target_dir) and not os.path.islink(target_dir):
            subprocess.run(["git", "-C", target_dir, "pull"], check=True, capture_output=True)
        else:
            if os.path.islink(target_dir): os.remove(target_dir)
            subprocess.run(["git", "clone", repo, target_dir], check=True, capture_output=True)
        status = "live"
    except Exception as e:
        status = f"failed: {e}"

    dep = db.query(models.Deployment).filter(models.Deployment.name == name, models.Deployment.user == user).first()
    if dep:
        dep.repo_url = repo; dep.status = status; dep.last_deployed = datetime.utcnow()
    else:
        dep = models.Deployment(user=user, name=name, repo_url=repo, domain_id=domain.id, status=status)
        db.add(dep)
    
    db.commit()
    return {"status": status, "deployment_id": dep.id}