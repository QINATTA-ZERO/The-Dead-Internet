#!/bin/bash
# Script to launch Chrome connected to the Dead Internet

BRIDGE="psx-bridge"

echo "Applying system DNS resolution for .psx domains on $BRIDGE..."
sudo resolvectl dns "$BRIDGE" 127.0.0.99
sudo resolvectl domain "$BRIDGE" "~psx"

USER_DATA_DIR="/tmp/dead-internet-browser-profile"

echo "Launching Chrome..."
google-chrome \
    --user-data-dir="$USER_DATA_DIR" \
    --no-first-run \
    http://www.psx &

echo "Browser launched. Direct .psx access via system DNS is active."

