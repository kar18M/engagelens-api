#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
#  EngageLens API — Quick Update Script
#  Run this whenever you push new code changes to GitHub.
#  Much faster than full redeploy (no Docker rebuild).
#
#  Usage (on the Oracle VM):
#    sudo /opt/engagelens/deploy/oracle_update.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }

APP_DIR="/opt/engagelens"
IMAGE_NAME="engagelens-api"
CONTAINER_NAME="engagelens"
PORT="8000"

info "Pulling latest code..."
git -C "$APP_DIR" pull origin main

info "Rebuilding image..."
docker build -t "$IMAGE_NAME" "$APP_DIR"

info "Restarting container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "$PORT:$PORT" \
    -e PORT="$PORT" \
    --env-file "$APP_DIR/.env" \
    -v "/opt/engagelens-data:/data" \
    "$IMAGE_NAME"

sleep 3
docker logs --tail 20 "$CONTAINER_NAME"
success "Update complete! Running on port $PORT."
