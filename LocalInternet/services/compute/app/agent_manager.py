#!/usr/bin/env python3
import sys
import os
import subprocess
import requests

TOKEN_DIR = "/etc/psx/tokens"
ID_API = "http://id.psx/api/register"
TOKEN_API = "http://id.psx/api/system/token"
SYSTEM_SECRET = os.getenv("SYSTEM_SECRET", "system-master-secret-key")

def create_agent(name, password):
    print(f"Creating Agent: {name}")
    
    # 1. Create Linux User
    try:
        # Check if user exists
        subprocess.run(["id", name], check=False, capture_output=True)
        if subprocess.run(["id", name], check=False).returncode != 0:
            subprocess.run(["useradd", "-m", "-s", "/bin/bash", name], check=True)
            subprocess.run(["chmod", "700", f"/home/{name}"], check=True)
    except Exception as e:
        print(f"Error creating user: {e}")

    # 2. Register with ID Service
    try:
        requests.post(ID_API, params={"username": name, "password": password})
    except Exception as e:
        print(f"ID registration skip/fail: {e}")

    # 3. Get Persistent Token
    try:
        resp = requests.post(TOKEN_API, params={"username": name, "secret": SYSTEM_SECRET})
        resp.raise_for_status()
        token = resp.json()["access_token"]
        
        os.makedirs(TOKEN_DIR, exist_ok=True)
        token_path = os.path.join(TOKEN_DIR, name)
        with open(token_path, "w") as f:
            f.write(token)
        os.chmod(token_path, 0o600)
        print(f"Token saved to {token_path}")
    except Exception as e:
        print(f"Error retrieving token: {e}")
        return

    # 4. Configure .bashrc (Prepend to ensure it runs even if non-interactive returns early)
    try:
        # Get UID
        uid_res = subprocess.run(["id", "-u", name], capture_output=True, text=True, check=True)
        uid = int(uid_res.stdout.strip())
        proxy_port = 10000 + uid
        
        bashrc_path = f"/home/{name}/.bashrc"
        config = f"""
# --- PSX Network Configuration START ---
export http_proxy=http://127.0.0.1:{proxy_port}
export https_proxy=http://127.0.0.1:{proxy_port}
export no_proxy=localhost,127.0.0.1
# --- PSX Network Configuration END ---
"""
        # Read existing
        content = ""
        if os.path.exists(bashrc_path):
            with open(bashrc_path, "r") as f:
                content = f.read()
        
        # Prepend
        with open(bashrc_path, "w") as f:
            f.write(config + content)
    except Exception as e:
        print(f"Error configuring bashrc: {e}")
    
    print(f"Agent {name} is ready.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: ./agent_manager.py <name> <password>")
        sys.exit(1)
    create_agent(sys.argv[1], sys.argv[2])