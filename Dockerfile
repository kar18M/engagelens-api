# ── EngageLens API — Docker Image ─────────────────────────────────────────────
#
# Works on:
#   • Render.com   (PORT env var set automatically, persistent disk at /data path)
#   • HF Spaces    (port 7860, persistent /data volume)
#   • Local        (docker run -p 8000:8000 -e PORT=8000 ...)
#
# InsightFace buffalo_l model (~500 MB) downloads to INSIGHTFACE_HOME on first boot.
# Set INSIGHTFACE_HOME to a persistent volume path so it only downloads once.
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

# System deps for OpenCV + InsightFace
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        wget \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements_hf.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create default data dir (overridden by mounted persistent volume)
RUN mkdir -p /data/enrolled_faces /data/.insightface

# Default env vars (override via platform secrets/env)
ENV DB_BACKEND=supabase
ENV ENROLLED_FACES_DIR=/data/enrolled_faces
ENV INSIGHTFACE_HOME=/data/.insightface

# PORT: Render sets this automatically. HF Spaces uses 7860. Default 8000 for local.
EXPOSE 8000 7860

# Use shell form so $PORT is expanded at runtime
CMD uvicorn engagelens-api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1

