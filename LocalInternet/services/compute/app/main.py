from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import psutil
import pwd
import os
import time
import secrets
import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, os.getenv("ADMIN_PASSWORD", "password"))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def get_uptime():
    return str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time())))

def get_agent_processes():
    agents = {}
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'create_time']):
        try:
            pinfo = proc.info
            username = pinfo['username']
            if not username: continue
            
            # Filter for agent users (uid >= 1000 and not nobody)
            try:
                user_pw = pwd.getpwnam(username)
                if user_pw.pw_uid < 1000 or username == "nobody":
                    continue
            except KeyError:
                continue

            if username not in agents:
                agents[username] = {"cpu": 0.0, "mem": 0, "procs": []}
            
            agents[username]["cpu"] += pinfo['cpu_percent']
            agents[username]["mem"] += pinfo['memory_info'].rss
            pinfo['uptime'] = str(datetime.timedelta(seconds=int(time.time() - pinfo['create_time'])))
            agents[username]["procs"].append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return agents

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/stats")
def api_stats(username: str = Depends(get_current_username)):
    agents = get_agent_processes()
    
    # Format agents for JSON
    agent_list = []
    for name, data in agents.items():
        agent_list.append({
            "user": name,
            "proc_count": len(data['procs']),
            "cpu": round(data['cpu'], 1),
            "mem_mb": round(data['mem'] / 1024 / 1024, 1),
            "procs": sorted(data['procs'], key=lambda x: x['cpu_percent'], reverse=True)[:5]
        })

    disk = psutil.disk_usage('/')
    
    return {
        "system": {
            "cpu": psutil.cpu_percent(),
            "mem": psutil.virtual_memory().percent,
            "disk": disk.percent,
            "uptime": get_uptime(),
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        },
        "agents": sorted(agent_list, key=lambda x: x['cpu'], reverse=True)
    }