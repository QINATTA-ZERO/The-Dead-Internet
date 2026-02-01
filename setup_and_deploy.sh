#!/bin/bash
set -e

# The Dead Internet - Deployment Script
echo "[*] Starting The Dead Internet deployment..."

# 1. Environment Configuration
if [ ! -f .env ]; then
    echo "[*] .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "[!] Created .env from .env.example. PLEASE EDIT IT and add your GEMINI_API_KEY if you haven't already."
    else
        echo "[ERROR] .env.example not found. Cannot create .env."
        exit 1
    fi
fi

# 2. Cleanup (Optional but recommended for a fresh start)
if [ "$1" == "--reset" ]; then
    echo "[!!!] WARNING: Total reset requested."
    cd LocalInternet
    docker compose down
    sudo rm -rf data
    mkdir -p data
    sudo rm -rf ../AgentsFramework/data
    mkdir -p ../AgentsFramework/data
    cp dns/db.psx.example dns/db.psx
    
    # Pre-download Nexus Model
    echo "[*] Downloading Nexus semantic model..."
    python3 download_model.py
    
    cd ..
fi

# 3. Boot the Grid
echo "[*] Spinning up the universe..."
cd LocalInternet
docker compose up -d

# 4. Wait for Database and Initialize
echo "[*] Waiting for database to be healthy..."
until [ "$(docker inspect -f {{.State.Health.Status}} dead-postgres)" == "healthy" ]; do
    echo -n "."
    sleep 2
done
echo -e "\n[+] Database is healthy."

# 5. Ensure required databases exist
echo "[*] Initializing additional databases..."
docker exec dead-postgres psql -U admin -d postgres -c "CREATE DATABASE forgejo;" 2>/dev/null || echo "[*] Database 'forgejo' already exists."
# psx_core is created by default from docker-compose.yml env

# 6. Success
echo ""
echo "===================================================="
echo "[SUCCESS] The Dead Internet is online!"
echo "===================================================="
echo "You can now jack in using the Model Context Protocol."
echo "Check container status: docker ps"
echo "===================================================="
