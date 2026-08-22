#!/usr/bin/env bash
# EngageLens — Start Script
# Usage: bash run.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"

# ── Load secrets from .env (if present) ───────────────────────────────────────
# .env holds TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME.
# It is listed in .gitignore and must never be committed.
# Variables already set in the shell environment take priority.
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    # Export each non-comment, non-blank line as an env variable
    set -o allexport
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +o allexport
    echo "✅ Loaded secrets from .env"
else
    echo "ℹ️  No .env file found — TELEGRAM_BOT_TOKEN must be set in the shell environment."
fi

# ── Activate virtual environment ──────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "ERROR: venv not found at $VENV"
    echo "Run:  python3.10 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

source "$VENV/bin/activate"

# ── Check MongoDB ──────────────────────────────────────────────────────────────
if ! mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
    echo "WARNING: MongoDB does not appear to be running."
    echo "Start it with:  sudo systemctl start mongod"
    echo "Continuing anyway — the app will show an error banner if DB is unreachable."
fi

# ── Print active Telegram config (masked token for safety) ────────────────────
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    TOKEN_MASKED="${TELEGRAM_BOT_TOKEN:0:10}…(masked)"
    echo "📨 Telegram bot  : @${TELEGRAM_BOT_USERNAME:-KarthickLeetBot}"
    echo "🔑 Token         : $TOKEN_MASKED"
else
    echo "⚠️  TELEGRAM_BOT_TOKEN not set — absentee alerts will be disabled."
fi

# ── Launch Streamlit ───────────────────────────────────────────────────────────
echo "Starting EngageLens at http://localhost:8501"
cd "$PROJECT_DIR"
streamlit run app.py \
    --server.port 8501 \
    --server.headless false \
    --browser.gatherUsageStats false
