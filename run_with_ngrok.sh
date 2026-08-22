#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_with_ngrok.sh
# Starts EngageLens + ngrok tunnel simultaneously.
#
# Usage:
#   bash run_with_ngrok.sh              # uses saved authtoken
#   NGROK_AUTHTOKEN=<token> bash run_with_ngrok.sh
#
# The public URL is printed to the terminal and written to ngrok_url.txt
# ─────────────────────────────────────────────────────────────────────────────

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
NGROK="$DIR/ngrok"

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ -f "$DIR/.env" ]; then
    export $(grep -v '^#' "$DIR/.env" | xargs) 2>/dev/null
fi

# ── Check ngrok binary ────────────────────────────────────────────────────────
if [ ! -f "$NGROK" ]; then
    echo "❌ ngrok binary not found at $NGROK"
    echo "   Run: bash install_ngrok.sh"
    exit 1
fi

# ── Check authtoken ───────────────────────────────────────────────────────────
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "❌ NGROK_AUTHTOKEN not set."
    echo ""
    echo "   1. Sign up free at: https://dashboard.ngrok.com/signup"
    echo "   2. Copy your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   3. Add to your .env file:  NGROK_AUTHTOKEN=your_token_here"
    echo "   4. Re-run this script."
    exit 1
fi

# ── Configure authtoken ───────────────────────────────────────────────────────
"$NGROK" config add-authtoken "$NGROK_AUTHTOKEN" 2>/dev/null

# ── Start EngageLens in the background ───────────────────────────────────────
echo ""
echo "🚀 Starting EngageLens..."
bash "$DIR/run.sh" &
APP_PID=$!

# Wait for Streamlit to come up
sleep 4

# ── Start ngrok tunnel ────────────────────────────────────────────────────────
echo ""
echo "🌐 Starting ngrok tunnel on port 8501..."
"$NGROK" http 8501 --log=stdout --log-format=json &
NGROK_PID=$!

# Wait a moment for ngrok to get a URL
sleep 3

# ── Fetch and display the public URL ─────────────────────────────────────────
PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "$PUBLIC_URL" ]; then
    echo "  ✅ EngageLens is publicly accessible at:"
    echo ""
    echo "     👉  $PUBLIC_URL"
    echo ""
    echo "  Share this URL with anyone — works from any device,"
    echo "  any network (phone, tablet, another laptop)."
    echo ""
    # Save URL to file for reference
    echo "$PUBLIC_URL" > "$DIR/ngrok_url.txt"
    echo "  URL also saved to: ngrok_url.txt"
else
    echo "  ⚠️  Could not retrieve public URL automatically."
    echo "  Open http://127.0.0.1:4040 in your browser to see the URL."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Press Ctrl+C to stop everything."
echo ""

# ── Keep alive — kill both processes on Ctrl+C ────────────────────────────────
trap "echo ''; echo '🛑 Stopping...'; kill $APP_PID $NGROK_PID 2>/dev/null; exit 0" INT TERM

wait
