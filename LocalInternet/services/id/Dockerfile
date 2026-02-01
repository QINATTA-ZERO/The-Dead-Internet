FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We mount the app code via volume in dev, but for a "real" feel
# we copy it here as a fallback or for production builds.
COPY app /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
