#!/usr/bin/env python3
import sys
import os
import re

ZONE_FILE = "dns/db.psx"

def register_domain(domain, ip):
    if not domain.endswith(".psx"):
        print("Error: Only .psx domains are allowed.")
        return

    # Basic validation
    if not re.match(r"^[a-z0-9-]+\.psx$", domain):
        print("Error: Invalid domain format.")
        return

    # Check if exists
    with open(ZONE_FILE, "r") as f:
        content = f.read()
        # Simple check, could be more robust
        if f"{domain.replace('.psx', '')} " in content or f"{domain.replace('.psx', '')}\t" in content:
            print(f"Error: Domain {domain} probably already registered.")
            # We don't return here to allow overwrites/additions if user really wants, 
            # but for a simple registrar we might want to block. 
            # For now let's just warn but proceed? No, let's block to be safe.
            return

    # Append
    # Format: subdomain IN A IP
    subdomain = domain.replace(".psx", "")
    entry = f"{subdomain:<8} IN  A   {ip}\n"
    
    with open(ZONE_FILE, "a") as f:
        f.write(entry)
    
    print(f"Successfully registered {domain} -> {ip}")
    print("DNS will reload in ~5 seconds.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: ./registrar.py <domain.psx> <ip>")
        sys.exit(1)
    
    register_domain(sys.argv[1], sys.argv[2])
