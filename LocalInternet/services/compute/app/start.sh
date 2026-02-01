#!/bin/bash
# Start the Transparent Proxy in the background
echo "Starting Proxy..."
python3 -u /app/proxy.py &

# Start the Dashboard Web Server in the background
echo "Starting Dashboard..."
uvicorn main:app --host 0.0.0.0 --port 80 &

# Keep the container running
wait
