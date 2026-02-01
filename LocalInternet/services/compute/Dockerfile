FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    iputils-ping \
    vim \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install aiohttp requests

WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY app/ /app/
RUN chmod +x /app/agent_manager.py /app/start.sh

# Install the PSX Browser Library globally
RUN cp /app/psx.py /usr/local/lib/python3.10/dist-packages/psx.py

# Create 'web' CLI tool
RUN echo '#!/bin/sh\npython3 /usr/local/lib/python3.10/dist-packages/psx.py "$@"' > /usr/local/bin/web && chmod +x /usr/local/bin/web

# Create tokens directory
RUN mkdir -p /etc/psx/tokens && chmod 700 /etc/psx/tokens

# Start services
CMD ["/app/start.sh"]
