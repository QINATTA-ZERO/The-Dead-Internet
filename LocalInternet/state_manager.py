#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import shutil
import argparse

# Config
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
HOSTED_SITES = os.path.join(PROJECT_ROOT, "services", "aether", "hosted_sites")
DNS_FILE = os.path.join(PROJECT_ROOT, "dns", "db.psx")
DNS_EXAMPLE = os.path.join(PROJECT_ROOT, "dns", "db.psx.example")
AGENTS_DATA = os.path.join(os.path.dirname(PROJECT_ROOT), "AgentsFramework", "data")
SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, "snapshots")

def run_cmd(cmd, check=True):
    print(f"[*] Executing: {" ".join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)

def snapshot():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = os.path.join(SNAPSHOT_DIR, f"snapshot_{ts}")
    os.makedirs(snap_path, exist_ok=True)

    print(f"[*] Creating full internet snapshot at {snap_path}...")

    # 1. Database Dump (All databases: psx_core, forgejo, etc)
    try:
        db_file = os.path.join(snap_path, "psx_full_cluster.sql")
        with open(db_file, "w") as f:
            # pg_dumpall captures all databases, users, and roles
            subprocess.run(["docker", "exec", "dead-postgres", "pg_dumpall", "-U", "admin"], stdout=f, check=True)
        print("[+] All databases dumped (psx_core + forgejo + accounts).")
    except Exception as e:
        print(f"[!] Database dump failed: {e}")

    # 2. DNS File
    if os.path.exists(DNS_FILE):
        shutil.copy2(DNS_FILE, os.path.join(snap_path, "db.psx"))
        print("[+] DNS zone copied.")

    # 3. Data Folders (Repos, Cache, Configs)
    print("[*] Archiving service persistent data...")
    run_cmd(["sudo", "tar", "-czf", os.path.join(snap_path, "service_data.tar.gz"), "-C", PROJECT_ROOT, "data", "services/aether/hosted_sites"])
    
    # 4. Agents
    if os.path.exists(AGENTS_DATA):
        print("[*] Archiving agent identities and memories...")
        run_cmd(["sudo", "tar", "-czf", os.path.join(snap_path, "agents_data.tar.gz"), "-C", os.path.dirname(AGENTS_DATA), "data"])

    print(f"\n[SUCCESS] Full Snapshot complete: {snap_path}")
    print("This snapshot contains all service data, repositories, accounts, and agent states.")

def reset():
    print("[!!!] WARNING: This will PERMANENTLY DELETE all internet data.")
    print("Includes: All Identities, VOX Balances, Echo Posts, Git Repos, Registered Domains, and Agent Memories.")
    confirm = input("Type 'RESET' to confirm total deletion: ")
    if confirm != "RESET":
        print("[*] Reset cancelled.")
        return

    print("[*] Initializing total reset sequence...")

    # 1. Stop Containers
    run_cmd(["docker", "compose", "down"], check=False)

    # 2. Wipe Data
    print("[*] Wiping persistent volumes...")
    run_cmd(["sudo", "rm", "-rf", DATA_DIR])
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 3. Reset Hosted Sites
    print("[*] Cleaning hosted sites...")
    if os.path.exists(HOSTED_SITES):
        for item in os.listdir(HOSTED_SITES):
            if item not in ["default_placeholder", "errors"]:
                path = os.path.join(HOSTED_SITES, item)
                if os.path.islink(path) or os.path.isfile(path):
                    os.unlink(path)
                else:
                    shutil.rmtree(path)

    # 4. Reset Agents
    print("[*] Wiping agent memories and identities...")
    if os.path.exists(AGENTS_DATA):
        run_cmd(["sudo", "rm", "-rf", AGENTS_DATA])
        os.makedirs(AGENTS_DATA, exist_ok=True)

    # 5. Restore DNS
    if os.path.exists(DNS_EXAMPLE):
        print("[*] Restoring default DNS records...")
        shutil.copy2(DNS_EXAMPLE, DNS_FILE)

    # 6. Restart
    print("[*] Re-spinning the universe...")
    run_cmd(["docker", "compose", "up", "-d"])
    
    # 7. Post-spin DB initialization (Forgejo needs its DB recreated)
    print("[*] Waiting for database to stabilize...")
    import time
    time.sleep(10)
    print("[*] Ensuring required databases exist...")
    run_cmd(["docker", "exec", "dead-postgres", "psql", "-U", "admin", "-d", "postgres", "-c", "CREATE DATABASE forgejo;"], check=False)
    run_cmd(["docker", "exec", "dead-postgres", "psql", "-U", "admin", "-d", "postgres", "-c", "CREATE DATABASE psx_core;"], check=False)

    print("\n[SUCCESS] The Dead Internet has been wiped and reset to zero state.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dead Internet State Manager")
    parser.add_argument("command", choices=["snapshot", "reset"], help="Action to perform")
    args = parser.parse_args()

    if args.command == "snapshot":
        snapshot()
    elif args.command == "reset":
        reset()