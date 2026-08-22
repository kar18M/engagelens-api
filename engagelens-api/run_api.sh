#!/usr/bin/env bash
# run_api.sh — Start the EngageLens FastAPI server
#
# Usage:
#   chmod +x run_api.sh
#   ./run_api.sh
#
# The API will be reachable at:
#   http://localhost:8000        (on this machine)
#   http://<your-ip>:8000       (from the smartboard on the same WiFi)
#   http://<your-ip>:8000/docs  (Swagger UI)
#
# Set your WiFi IP below or use $(hostname -I | awk '{print $1}') for auto-detect.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate the existing venv if it exists
if [ -f "$PARENT_DIR/venv/bin/activate" ]; then
    echo "Activating venv at $PARENT_DIR/venv"
    source "$PARENT_DIR/venv/bin/activate"
fi

# Install API-specific deps if not yet installed
pip install -q fastapi "uvicorn[standard]" python-jose passlib python-multipart psutil 2>/dev/null

# Detect local IP for display
LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "============================================================"
echo "  EngageLens FastAPI Server"
echo "  Local:      http://localhost:8000"
echo "  Network:    http://$LOCAL_IP:8000"
echo "  Swagger UI: http://$LOCAL_IP:8000/docs"
echo "  Set Flutter BASE_URL to: http://$LOCAL_IP:8000"
echo "============================================================"
echo ""

cd "$SCRIPT_DIR"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
