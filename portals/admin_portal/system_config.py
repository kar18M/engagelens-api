"""
portals/admin_portal/system_config.py
=======================================
Admin — Live System Configuration Editor (Phase 10).

Allows admin to edit config.py values in-session and at runtime.
Changes are logged to audit_log. Does NOT write back to config.py file —
values are stored in MongoDB `system_config` collection and override
config.py defaults at runtime (for the current process only; restart
required for new processes unless app.py reads from DB on startup).
"""

import streamlit as st
import config
from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("admin")
update_last_activity()

st.markdown("""
<style>
.admin-badge {
    background: var(--bg2);
    border: 1px solid var(--border);
    color: var(--dark);
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 10px;
}
.status-ok  { color: #2D6A4F; font-weight: 600; }
.status-err { color: #991B1B; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

user = get_current_user()
actor_id = user.get("user_id", "admin")

from auth.user_operations import log_audit
from database.mongo_client import get_db

db = get_db()

st.markdown('<div class="admin-badge">🛠️ ADMIN PORTAL</div>', unsafe_allow_html=True)
st.title("⚙️ System Configuration")
st.caption(
    "Edit runtime configuration values. Changes take effect immediately for the current session "
    "and are stored in MongoDB. A process restart is required for new Streamlit sessions to pick up changes."
)
st.divider()

# ── Load overrides from DB ────────────────────────────────────────────────────
def _get_config_overrides() -> dict:
    doc = db["system_config"].find_one({"_id": "runtime"}, {"_id": 0})
    return doc or {}

def _save_config_override(key: str, value, actor_id: str, old_value) -> None:
    db["system_config"].update_one(
        {"_id": "runtime"},
        {"$set": {key: value}},
        upsert=True,
    )
    log_audit(
        actor_user_id=actor_id,
        actor_role="admin",
        action="config_changed",
        target=f"config.{key}",
        old_value=str(old_value),
        new_value=str(value),
    )

overrides = _get_config_overrides()

def _val(key: str, default):
    """Return DB override if present, else config.py default."""
    return overrides.get(key, default)

# ── Config sections ────────────────────────────────────────────────────────────
with st.form("config_form"):
    st.markdown("### 🔍 Face Recognition")
    col1, col2 = st.columns(2)

    new_threshold = col1.slider(
        "Recognition Threshold (cosine distance)",
        min_value=0.20, max_value=0.70,
        value=float(_val("RECOGNITION_THRESHOLD", config.RECOGNITION_THRESHOLD)),
        step=0.01,
        help="Lower = stricter. Increase if too many unknowns; decrease if false positives.",
    )
    new_min_face = col2.number_input(
        "Min Face Size (px)",
        min_value=10, max_value=200,
        value=int(_val("MIN_FACE_SIZE_PX", config.MIN_FACE_SIZE_PX)),
        help="Minimum bounding box height for face detection.",
    )

    st.markdown("### 🔲 Tiling (Batch Mode)")
    col3, col4, col5 = st.columns(3)
    new_tile_size = col3.number_input(
        "Tile Size (px)",
        min_value=320, max_value=1280,
        value=int(_val("TILE_SIZE", config.TILE_SIZE)),
        step=32,
    )
    new_tile_overlap = col4.number_input(
        "Tile Overlap (px)",
        min_value=0, max_value=320,
        value=int(_val("TILE_OVERLAP", config.TILE_OVERLAP)),
        step=8,
    )
    new_iou = col5.slider(
        "IoU NMS Threshold",
        min_value=0.1, max_value=0.9,
        value=float(_val("IOU_THRESHOLD", config.IOU_THRESHOLD)),
        step=0.05,
    )

    st.markdown("### 🧑‍🎓 Enrollment")
    col6, col7 = st.columns(2)
    new_min_angles = col6.number_input(
        "Min Enrollment Angles",
        min_value=1, max_value=5,
        value=int(_val("MIN_ENROLLMENT_ANGLES", config.MIN_ENROLLMENT_ANGLES)),
    )
    new_frame_skip = col7.number_input(
        "Live Frame Skip",
        min_value=1, max_value=10,
        value=int(_val("FRAME_SKIP", config.FRAME_SKIP)),
        help="Process 1 in every N frames in live mode.",
    )

    st.markdown("### 🔐 Auth & Sessions")
    col8, col9, col10 = st.columns(3)
    new_session_timeout = col8.number_input(
        "Session Timeout (minutes)",
        min_value=5, max_value=480,
        value=int(_val("SESSION_TIMEOUT_MINUTES", config.SESSION_TIMEOUT_MINUTES)),
    )
    new_max_attempts = col9.number_input(
        "Max Login Attempts",
        min_value=3, max_value=20,
        value=int(_val("MAX_LOGIN_ATTEMPTS", config.MAX_LOGIN_ATTEMPTS)),
    )
    new_lockout = col10.number_input(
        "Lockout Duration (minutes)",
        min_value=1, max_value=60,
        value=int(_val("LOCKOUT_DURATION_MINUTES", config.LOCKOUT_DURATION_MINUTES)),
    )

    st.markdown("### 📊 Attendance")
    new_warn_threshold = st.slider(
        "Student Attendance Warning Threshold (%)",
        min_value=50, max_value=100,
        value=int(_val("ATTENDANCE_WARNING_THRESHOLD", config.ATTENDANCE_WARNING_THRESHOLD)),
        step=5,
        help="Students below this % see a warning on their dashboard.",
    )

    st.divider()
    c_save, c_reset = st.columns(2)
    save_submitted  = c_save.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
    reset_submitted = c_reset.form_submit_button("↩️ Reset to Defaults", type="secondary", use_container_width=True)

if save_submitted:
    changes = {
        "RECOGNITION_THRESHOLD":      new_threshold,
        "MIN_FACE_SIZE_PX":           new_min_face,
        "TILE_SIZE":                  new_tile_size,
        "TILE_OVERLAP":               new_tile_overlap,
        "IOU_THRESHOLD":              new_iou,
        "MIN_ENROLLMENT_ANGLES":      new_min_angles,
        "FRAME_SKIP":                 new_frame_skip,
        "SESSION_TIMEOUT_MINUTES":    new_session_timeout,
        "MAX_LOGIN_ATTEMPTS":         new_max_attempts,
        "LOCKOUT_DURATION_MINUTES":   new_lockout,
        "ATTENDANCE_WARNING_THRESHOLD": new_warn_threshold,
    }
    for key, new_val in changes.items():
        old_val = overrides.get(key, getattr(config, key, "?"))
        if new_val != old_val:
            _save_config_override(key, new_val, actor_id, old_val)
            # Apply immediately to this process
            setattr(config, key, new_val)

    st.success("✅ Configuration saved and applied to this session.", icon="✅")

if reset_submitted:
    db["system_config"].delete_one({"_id": "runtime"})
    log_audit(
        actor_user_id=actor_id,
        actor_role="admin",
        action="config_changed",
        target="ALL",
        old_value=str(overrides),
        new_value="RESET_TO_DEFAULTS",
    )
    st.success("✅ All config values reset to code defaults.", icon="✅")
    st.rerun()

st.divider()

# ── Current values display ────────────────────────────────────────────────────
st.markdown("### Current Values")
import pandas as pd
current = _get_config_overrides()
config_items = [
    ("RECOGNITION_THRESHOLD",      getattr(config, "RECOGNITION_THRESHOLD", "?")),
    ("MIN_FACE_SIZE_PX",           getattr(config, "MIN_FACE_SIZE_PX", "?")),
    ("TILE_SIZE",                  getattr(config, "TILE_SIZE", "?")),
    ("TILE_OVERLAP",               getattr(config, "TILE_OVERLAP", "?")),
    ("IOU_THRESHOLD",              getattr(config, "IOU_THRESHOLD", "?")),
    ("MIN_ENROLLMENT_ANGLES",      getattr(config, "MIN_ENROLLMENT_ANGLES", "?")),
    ("FRAME_SKIP",                 getattr(config, "FRAME_SKIP", "?")),
    ("SESSION_TIMEOUT_MINUTES",    getattr(config, "SESSION_TIMEOUT_MINUTES", "?")),
    ("MAX_LOGIN_ATTEMPTS",         getattr(config, "MAX_LOGIN_ATTEMPTS", "?")),
    ("LOCKOUT_DURATION_MINUTES",   getattr(config, "LOCKOUT_DURATION_MINUTES", "?")),
    ("ATTENDANCE_WARNING_THRESHOLD", getattr(config, "ATTENDANCE_WARNING_THRESHOLD", "?")),
]
rows = [
    {"Setting": k, "Value": str(v), "Overridden": "✅ Yes" if k in current else "— Default"}
    for k, v in config_items
]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.caption(f"EngageLens v2.0 · Admin Portal · {user.get('full_name','')}")
