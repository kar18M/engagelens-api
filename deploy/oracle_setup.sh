#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
#  EngageLens API — Oracle Cloud Free Tier Setup Script
#  Run this ONCE on a fresh Oracle Cloud Ubuntu 22.04 VM (Ampere A1 ARM)
#
#  Usage:
#    chmod +x oracle_setup.sh
#    sudo ./oracle_setup.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

# ── Colors for output ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   EngageLens API — Oracle Cloud Setup Script     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. System Update ───────────────────────────────────────────────────────────
info "Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq
success "System updated."

# ── 2. Install Docker ──────────────────────────────────────────────────────────
info "Installing Docker..."
if command -v docker &>/dev/null; then
    warn "Docker already installed. Skipping."
else
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    success "Docker installed."
fi

# Add current user to docker group (so ubuntu user can run docker without sudo)
usermod -aG docker ubuntu 2>/dev/null || true

# ── 3. Open Firewall Ports ─────────────────────────────────────────────────────
info "Configuring firewall (iptables)..."
# Oracle Cloud also requires Security List rules in the OCI console (see guide)
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 7860 -j ACCEPT 2>/dev/null || true
# Save rules so they persist across reboots
apt-get install -y -qq iptables-persistent
netfilter-persistent save
success "Firewall ports 8000 and 7860 opened."

# ── 4. Create App Directory ────────────────────────────────────────────────────
APP_DIR="/opt/engagelens"
DATA_DIR="/opt/engagelens-data"

info "Creating app directories..."
mkdir -p "$APP_DIR" "$DATA_DIR/enrolled_faces" "$DATA_DIR/.insightface"
chown -R ubuntu:ubuntu "$APP_DIR" "$DATA_DIR"
success "Directories created at $APP_DIR and $DATA_DIR."

# ── 5. Clone / Update the Repository ──────────────────────────────────────────
info "Cloning EngageLens repository..."
REPO_URL="https://github.com/kar18M/engagelens-api.git"

if [ -d "$APP_DIR/.git" ]; then
    warn "Repo already cloned. Pulling latest changes..."
    git -C "$APP_DIR" pull origin main
else
    git clone "$REPO_URL" "$APP_DIR"
fi
chown -R ubuntu:ubuntu "$APP_DIR"
success "Repository ready at $APP_DIR."

# ── 6. Create .env File ────────────────────────────────────────────────────────
info "Creating .env file..."
if [ -f "$APP_DIR/.env" ]; then
    warn ".env already exists. Skipping. Edit manually at $APP_DIR/.env if needed."
else
    cat > "$APP_DIR/.env" <<'ENV'
# EngageLens API — Production Secrets
# ⚠️  DO NOT commit this file to git

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL=https://fxuvwigazfzjgvjipkep.supabase.co
SUPABASE_ANON_KEY=REPLACE_WITH_ANON_KEY
SUPABASE_SERVICE_KEY=REPLACE_WITH_SERVICE_KEY

# ── Database Backend ──────────────────────────────────────────────────────────
DB_BACKEND=supabase

# ── Face Recognition Paths ────────────────────────────────────────────────────
ENROLLED_FACES_DIR=/data/enrolled_faces
INSIGHTFACE_HOME=/data/.insightface

# ── Telegram Notifications (optional) ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN=REPLACE_WITH_TOKEN

# ── JWT Secret ────────────────────────────────────────────────────────────────
SECRET_KEY=REPLACE_WITH_RANDOM_SECRET_32_CHARS
ENV
    chown ubuntu:ubuntu "$APP_DIR/.env"
    warn ".env created. EDIT IT NOW: nano $APP_DIR/.env"
    echo ""
    echo -e "${YELLOW}  ┌─────────────────────────────────────────────────┐${NC}"
    echo -e "${YELLOW}  │  Fill in your real values in $APP_DIR/.env  │${NC}"
    echo -e "${YELLOW}  │  then run:  sudo /opt/engagelens/deploy/oracle_deploy.sh  │${NC}"
    echo -e "${YELLOW}  └─────────────────────────────────────────────────┘${NC}"
    echo ""
fi

success "Setup complete! Next steps:"
echo ""
echo "  1. Edit your secrets:  nano $APP_DIR/.env"
echo "  2. Deploy:             sudo $APP_DIR/deploy/oracle_deploy.sh"
echo ""
