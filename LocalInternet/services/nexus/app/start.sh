#!/bin/bash
set -e

CACHE_DIR="/cache"
MODEL_NAME="BAAI/bge-small-en-v1.5"

# Check if model is already downloaded (simple directory check)
# FastEmbed usually creates a directory starting with 'models--'
if [ -z "$(ls -A $CACHE_DIR 2>/dev/null)" ]; then
    echo "[*] Nexus Cache is empty. Provisioning Semantic Brain ($MODEL_NAME)..."
    # Temporarily allow internet access for download
    export HF_HUB_OFFLINE=0
    python3 -c "import os; from fastembed import TextEmbedding; os.environ['FASTEMBED_CACHE_PATH'] = '$CACHE_DIR'; TextEmbedding(model_name='$MODEL_NAME')"
    echo "[+] Provisioning complete."
else
    echo "[*] Nexus Cache detected. Starting in offline mode."
fi

# Start the application
echo "[*] Launching Nexus Brain..."
exec uvicorn main:app --host 0.0.0.0 --port 80
