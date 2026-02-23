#!/bin/bash
set -e
echo "================================================"
echo " LeavePass — Production Deploy"
echo "================================================"
echo "→ Pulling latest code from GitHub..."
git pull origin main
echo "→ Rebuilding Docker containers..."
docker compose -p leave-prod -f docker-compose.prod.yml down
docker compose -p leave-prod -f docker-compose.prod.yml build
docker compose -p leave-prod -f docker-compose.prod.yml up -d
echo "✓ Deployment complete."
echo "================================================"
