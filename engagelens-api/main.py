"""
engagelens-api/main.py
======================
FastAPI application entry point for EngageLens.

Works in three environments:
  1. Local (dev)     — uvicorn main:app --port 8000
  2. Hugging Face Spaces — Docker, port 7860, /data persistent volume
  3. ngrok tunnel    — expose local port to internet
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load credentials from .env (works locally; on HF Spaces use Secrets UI) ──
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# ── Add the parent project to sys.path so we can reuse its modules ───────────
PARENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PARENT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, students, attendance, recognition, enroll, alerts, admin, classes

app = FastAPI(
    title="EngageLens API",
    description="REST backend for the EngageLens Face Recognition Attendance System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow Flutter app (any origin on same LAN) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict to specific IP in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ─────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/auth",       tags=["Auth"])
app.include_router(students.router,    prefix="/students",   tags=["Students"])
app.include_router(attendance.router,  prefix="/attendance", tags=["Attendance"])
app.include_router(recognition.router, prefix="/recognize",  tags=["Recognition"])
app.include_router(enroll.router,      prefix="/enroll",     tags=["Enrollment"])
app.include_router(alerts.router,      prefix="/alerts",     tags=["Alerts"])
app.include_router(admin.router,       prefix="/admin",      tags=["Admin"])
app.include_router(classes.router,     prefix="/classes",    tags=["Classes"])


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "EngageLens API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
