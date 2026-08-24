#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
#  EngageLens API — Deploy / Re-deploy Script
#  Run this to (re)deploy after setup or after any code changes.
#
#  Usage:
#    sudo /opt/engagelens/deploy/oracle_deploy.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

APP_DIR="/opt/engagelens"
DATA_DIR="/opt/engagelens-data"
IMAGE_NAME="engagelens-api"
CONTAINER_NAME="engagelens"
PORT="8000"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║      EngageLens API — Deploy Script              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Validate .env ──────────────────────────────────────────────────────────────
if grep -q "REPLACE_WITH" "$APP_DIR/.env"; then
    echo -e "${RED}[ERROR]${NC} .env still has placeholder values!"
    echo "  Edit: nano $APP_DIR/.env"
    exit 1
fi

# ── Pull latest code ───────────────────────────────────────────────────────────
info "Pulling latest code from GitHub..."
git -C "$APP_DIR" pull origin main
success "Code up to date."

# ── Stop existing container ────────────────────────────────────────────────────
info "Stopping existing container (if any)..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true
success "Old container removed."

# ── Build Docker image ─────────────────────────────────────────────────────────
info "Building Docker image (this takes ~5 min on first run for InsightFace)..."
docker build -t "$IMAGE_NAME" "$APP_DIR"
success "Docker image built."

# ── Run container ──────────────────────────────────────────────────────────────
info "Starting EngageLens API container on port $PORT..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "$PORT:$PORT" \
    -e PORT="$PORT" \
    --env-file "$APP_DIR/.env" \
    -v "$DATA_DIR:/data" \
    "$IMAGE_NAME"

success "Container started!"

# ── Install systemd service for auto-start on reboot ──────────────────────────
info "Installing systemd service for auto-start on reboot..."
cat > /etc/systemd/system/engagelens.service <<SYSTEMD
[Unit]
Description=EngageLens API (Docker)
After=docker.service
Requires=docker.service

[Service]
Restart=always
RestartSec=10
ExecStart=/usr/bin/docker start -a $CONTAINER_NAME
ExecStop=/usr/bin/docker stop $CONTAINER_NAME

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable engagelens
success "Systemd service installed and enabled."

# ── Show status ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  EngageLens API is LIVE!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_VM_IP")
echo "  🌐 API URL:    http://${PUBLIC_IP}:${PORT}"
echo "  📖 Docs:       http://${PUBLIC_IP}:${PORT}/docs"
echo "  ❤️  Health:     http://${PUBLIC_IP}:${PORT}/health"
echo ""
echo "  Useful commands:"
echo "    docker logs -f $CONTAINER_NAME    # View live logs"
echo "    docker stats $CONTAINER_NAME      # Memory/CPU usage"
echo "    sudo systemctl status engagelens  # Service status"
echo ""

# Wait a moment then show logs
sleep 3
info "Recent container logs:"
docker logs --tail 20 "$CONTAINER_NAME"
