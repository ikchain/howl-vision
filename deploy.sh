#!/usr/bin/env bash
set -euo pipefail

echo "=== Howl Vision — Deploy ==="

# Pull latest images
echo "[1/4] Pulling Docker images..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull 2>/dev/null || true
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Ensure Gemma 4 E4B is available in Ollama
echo "[2/4] Pulling Gemma 4 E4B via Ollama..."
ollama pull gemma4:e4b

# Start services
echo "[3/4] Starting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Wait for backend health
echo "[4/4] Waiting for backend health..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:20001/health > /dev/null 2>&1; then
        echo "Backend is healthy!"
        break
    fi
    sleep 2
done

echo ""
echo "=== Deploy complete ==="
echo "Frontend: http://localhost:20000"
echo "Backend:  http://localhost:20001"
echo "Vision:   http://localhost:20002"
