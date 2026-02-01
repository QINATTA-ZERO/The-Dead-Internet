#!/bin/bash
echo "Starting SMTP Server..."
python3 /app/smtp_server.py &

echo "Starting Webmail Dashboard..."
uvicorn main:app --host 0.0.0.0 --port 80 &

wait
