#!/bin/bash
set -e
echo "================================================"
echo " LeavePass — Deploy Script"
echo "================================================"
echo "→ Pulling latest code from USB..."
git pull usb main
echo "→ Rebuilding Docker containers..."
docker compose down
docker compose build
docker compose up -d
echo "✓ Deployment complete."
echo "================================================"
