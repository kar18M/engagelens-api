"""
EngageLens — Central Configuration
====================================
All tuneable constants live here. Change RECOGNITION_THRESHOLD to trade off
false-positives vs. false-negatives; lower distance = stricter match.

Phase 9 additions: TELEGRAM_* constants for FN/AN absentee alerts.
"""

import os
from pathlib import Path

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "engagelens"

# ── File Paths ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# On Hugging Face Spaces, set ENROLLED_FACES_DIR=/data/enrolled_faces (persistent volume)
# Locally it defaults to the project's data/enrolled_faces directory
_enrolled_env = os.environ.get("ENROLLED_FACES_DIR", "")
ENROLLED_FACES_DIR = Path(_enrolled_env) if _enrolled_env else DATA_DIR / "enrolled_faces"
ENROLLED_FACES_DIR.mkdir(parents=True, exist_ok=True)

# ── InsightFace Model ──────────────────────────────────────────────────────────
# buffalo_l auto-downloads on first run (~500 MB).  Needs internet once.
# Set INSIGHTFACE_HOME env-var to control download location.
INSIGHTFACE_MODEL  = "buffalo_l"
CTX_ID             = -1          # -1 = CPU, 0 = first GPU

# ── Recognition Tuning ────────────────────────────────────────────────────────
# ArcFace produces normalised 512-d embeddings.
# Cosine distance: 0 = identical, 2 = maximally different.
# Typical same-person distance: 0.20–0.40 (good lighting, front-on).
# Turned heads / lower quality: 0.40–0.50.
# Recommended starting threshold:  0.45 — lower is stricter.
RECOGNITION_THRESHOLD = 0.50

# Minimum bounding-box height (pixels in ORIGINAL full-res image) that the
# detector should still attempt.  Keeps tiny far-away faces in wide shots.
MIN_FACE_SIZE_PX = 15

# ── Live-Mode Frame Skipping ───────────────────────────────────────────────────
# Process only every Nth frame in live (WebRTC) mode to keep the stream smooth
# on CPU.  Batch/snapshot mode ignores this setting.
FRAME_SKIP = 3

# ── Tiling (Batch Processor) ──────────────────────────────────────────────────
# Tile size fed to the detector.  Larger = more context per tile, slower.
# 640 matches RetinaFace's default training input size.
TILE_SIZE    = 640
TILE_OVERLAP = 160  # pixels of overlap between adjacent tiles (prevents missed faces at edges)
IOU_THRESHOLD = 0.35  # IoU above this → keep only the higher-confidence detection

# ── Enrollment ────────────────────────────────────────────────────────────────
MIN_ENROLLMENT_ANGLES = 2   # front + at least one profile
VALID_ANGLES = ["front", "left_profile", "right_profile", "tilt_up", "tilt_down"]

# ── Telegram Notification (Phase 9) ───────────────────────────────────────────
# SECURITY: TELEGRAM_BOT_TOKEN must NEVER be hardcoded here.
# Set the environment variable before running:
#   export TELEGRAM_BOT_TOKEN="123456:ABC-your-token"
# Or place it in a .env file and load with python-dotenv.
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Bot username (without @) — used to build parent deep-link URL:
#   https://t.me/{TELEGRAM_BOT_USERNAME}?start={student_id}
TELEGRAM_BOT_USERNAME: str = os.environ.get("TELEGRAM_BOT_USERNAME", "KarthickLeetBot")

# ── Absentee Message Template ─────────────────────────────────────────────────
# Edit wording here; bot logic in notifications/telegram_bot.py reads this
# string and formats it — no bot code changes needed for rewording.
# Placeholders: {name}, {roll_no}, {class_section}, {session_full}, {date_display}
ABSENTEE_MESSAGE_TEMPLATE = (
    "Dear Parent,\n\n"
    "This is to inform you that your ward, {name} (Roll No: {roll_no}, "
    "{class_section}), was marked ABSENT for the {session_full} session "
    "on {date_display}.\n\n"
    "If this is unexpected, please contact the class in-charge.\n\n"
    "Regards,\n"
    "{class_section} Class In-Charge\n"
    "EngageLens Attendance System"
)

# ── Phase 10: Authentication & Role-Based Access ──────────────────────────────
SESSION_TIMEOUT_MINUTES      = 30    # Idle auto-logout window
PASSWORD_MIN_LENGTH          = 8     # Enforced on create / reset
MAX_LOGIN_ATTEMPTS           = 5     # Failed attempts before lockout
LOCKOUT_DURATION_MINUTES     = 15    # How long the lockout lasts
ATTENDANCE_WARNING_THRESHOLD = 75    # % below which student sees warning banner

# Valid roles
VALID_ROLES = ["student", "teacher", "admin"]
