#!/bin/bash
set -e

PROJECT=leave-app-prod
COMPOSE="docker compose -p $PROJECT -f docker-compose.prod.yml --env-file .env.prod"

echo "================================================"
echo " LeavePass — Production Deploy"
echo "================================================"

if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found. Copy .env.prod.example and fill in real values."
  exit 1
fi

echo "→ Pulling latest code from GitHub..."
git pull origin main

echo "→ Rebuilding Docker containers..."
$COMPOSE down
$COMPOSE build
$COMPOSE up -d

echo "✓ Deployment complete."
echo "================================================"
