# ── EngageLens API — Docker Image ─────────────────────────────────────────────
#
# Works on:
#   • Hugging Face Spaces  (port 7860, /data persistent volume)
#   • Render.com           (PORT env var set automatically)
#   • Local                (docker run -p 8000:8000 -e PORT=8000 ...)
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
        g++ \
        gcc \
        cmake \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ── HF Spaces requires a non-root user ──────────────────────────────────────
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements_hf.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create data dirs and hand ownership to non-root user
RUN mkdir -p /data/enrolled_faces /data/.insightface && \
    chown -R appuser:appuser /app /data

USER appuser

# Default env vars (override via platform secrets/env)
ENV DB_BACKEND=supabase
ENV ENROLLED_FACES_DIR=/data/enrolled_faces
ENV INSIGHTFACE_HOME=/data/.insightface

# HF Spaces uses 7860. Render sets PORT automatically. Default 7860.
EXPOSE 7860

# --app-dir tells uvicorn where main.py lives (inside engagelens-api/ subdir).
# This also adds engagelens-api/ to sys.path so 'from routers import ...' works.
CMD sh -c "uvicorn main:app --app-dir /app/engagelens-api --host 0.0.0.0 --port ${PORT:-7860} --workers 1"
