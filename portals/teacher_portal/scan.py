"""
portals/teacher_portal/scan.py
================================
Teacher — Batch Classroom Scan (Phase 10).
Ported from pages/2_Batch_Classroom_Scan.py with role guard added.
st.set_page_config removed (handled by app.py).
"""

import time
from datetime import date

import cv2
import numpy as np
import streamlit as st

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("teacher", "admin")
update_last_activity()



from database.mongo_client import get_db, MongoConnectionError
from database.db_operations import (
    get_all_students, mark_attendance_if_new, get_absentees, get_notification_log,
)
from notifications.telegram_bot import send_batch_alerts
from face_recognition_module.encodings_store import load_known_students
import batch_processor
import config as _cfg

@st.cache_resource(show_spinner="Loading recognition models…")
def _get_detector():
    from face_recognition_module.detector import load_detector
    try:
        return load_detector(), None
    except RuntimeError as exc:
        return None, str(exc)

detector, det_err = _get_detector()
if det_err:
    st.error(f"InsightFace failed to load: {det_err}", icon="⚠️")
    st.stop()

with st.sidebar:
    st.markdown("## ⚙️ Batch Settings")
    cam_source_raw = st.text_input("Camera Index / Stream URL", value="0")
    try:
        cam_source = int(cam_source_raw)
    except ValueError:
        cam_source = cam_source_raw

    capture_interval = st.slider("Capture interval (s)", 5, 120, 30, 5)
    upscale_factor   = st.slider("Tile upscale factor", 1, 4, 2, 1)
    threshold        = st.slider("Recognition threshold", 0.20, 0.70, 0.55, 0.01)
    st.divider()
    st.caption(f"Tile: {_cfg.TILE_SIZE}×{_cfg.TILE_SIZE} | Overlap: {int(_cfg.TILE_OVERLAP/_cfg.TILE_SIZE*100)}%")

st.title("📸 Batch Attendance Mode")
st.info(
    "Upload a classroom photo or capture from webcam. "
    "Designed for **large classrooms (30–60+ students)**.",
    icon="ℹ️",
)
st.divider()

# Session selector
session_label = st.radio("Session:", ["Forenoon (FN)", "Afternoon (AN)"], horizontal=True, key="scan_session")
SESSION_CODE = "FN" if "FN" in session_label else "AN"
TODAY_STR    = date.today().isoformat()
st.caption(f"📌 Recording **{session_label}** on **{TODAY_STR}**")
st.divider()

def _capture_webcam_frame(source):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return None, f"Could not open camera '{source}'."
    for _ in range(5):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None, "Camera returned empty frame."
    return frame, None

def _run_batch(frame, known_students, commit=True):
    if upscale_factor > 1:
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (w * upscale_factor, h * upscale_factor), interpolation=cv2.INTER_CUBIC)
    return batch_processor.process_classroom_image(
        image_source=frame,
        known_students=known_students,
        threshold=threshold,
        commit_attendance=commit,
        session=SESSION_CODE,
    )

def _show_result(output):
    if output["error"]:
        st.error(output["error"], icon="⚠️")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("👤 Detected",   output["n_detected"])
    c2.metric("✅ Recognised", output["n_recognised"])
    c3.metric("❓ Unknown",    output["n_unknown"])
    if output["annotated_image"] is not None:
        st.image(cv2.cvtColor(output["annotated_image"], cv2.COLOR_BGR2RGB),
                 caption="Detection Results", use_container_width=True)
    newly = output.get("attendance_new", [])
    if newly:
        st.success(f"Attendance marked for {len(newly)} new student(s): {', '.join(newly)}", icon="✅")

def _show_absentee_section(date_str, session):
    st.markdown(f"---\n### 📢 Absentee Alerts — {session}")
    with st.spinner("Computing absentees…"):
        absentees = get_absentees(date_str, session)
    if not absentees:
        st.success("All enrolled students present. No alerts needed.", icon="✅")
        return
    st.warning(f"**{len(absentees)} absentee(s)** for {session} on {date_str}.", icon="⚠️")
    import pandas as pd
    rows = []
    all_sent = True
    for s in absentees:
        log = get_notification_log(s["student_id"], date_str, session)
        if log and log.get("status") == "sent":
            status = "✅ Sent"
        elif s.get("parent_telegram_chat_id"):
            status = "⏳ Pending"
            all_sent = False
        else:
            status = "⚠️ No parent linked"
        rows.append({
            "Name": s["name"], "Roll No": s["roll_no"],
            "Parent Linked": "✅" if s.get("parent_telegram_chat_id") else "❌",
            "Alert Status": status,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if all_sent:
        st.success("All alerts already sent.", icon="✅")
    elif st.button(f"📨 Send Alerts ({len(absentees)} students)",
                   type="primary", key="batch_send_alerts"):
        with st.spinner("Sending…"):
            results = send_batch_alerts(absentees, date_str, session)
        for r in results:
            sname = next((s["name"] for s in absentees if s["student_id"] == r["student_id"]), r["student_id"])
            if r["status"] == "sent":
                st.success(f"✅ {sname}")
            elif r["status"] == "skipped_no_chat_id":
                st.warning(f"⚠️ {sname} — No parent linked")
            elif r["status"] == "failed":
                st.error(f"❌ {sname} — {r.get('error','')}")
        st.rerun()

# Load gallery
if "known_students" not in st.session_state:
    st.session_state["known_students"] = load_known_students()
known_students = st.session_state["known_students"]

if not known_students:
    st.warning("No students enrolled. Go to **Enroll Student** first.", icon="⚠️")

col_reload = st.columns([8, 2])[1]
if col_reload.button("🔄 Reload Gallery"):
    st.session_state["known_students"] = load_known_students()
    st.success(f"Gallery: {len(st.session_state['known_students'])} students.")
    st.rerun()

st.divider()

# Session state
for k, v in [("last_committed_session", None), ("last_committed_date", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

tab_webcam, tab_upload = st.tabs(["📷 Webcam Capture", "🖼️ Upload Photo"])

with tab_webcam:
    if st.button("📸 Capture Now", type="primary", key="capture_now_btn"):
        with st.spinner(f"Opening camera '{cam_source}'…"):
            frame, err = _capture_webcam_frame(cam_source)
        if err:
            st.error(err, icon="🔴")
        else:
            with st.spinner("Processing…"):
                output = _run_batch(frame, known_students, commit=True)
            _show_result(output)
            if not output["error"]:
                st.session_state["last_committed_session"] = SESSION_CODE
                st.session_state["last_committed_date"]    = TODAY_STR

with tab_upload:
    uploaded = st.file_uploader("Upload classroom photo", type=["jpg", "jpeg", "png", "webp"])
    if uploaded:
        file_bytes = np.frombuffer(uploaded.read(), np.uint8)
        image_bgr  = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image_bgr is None:
            st.error("Could not decode image.", icon="❌")
        else:
            h, w = image_bgr.shape[:2]
            st.caption(f"{uploaded.name} · {w}×{h} px")
            commit_upload = st.checkbox("Commit attendance after processing", value=True)
            if st.button("▶️ Process Image", type="primary", key="process_upload_btn"):
                with st.spinner("Processing…"):
                    output = _run_batch(image_bgr, known_students, commit=commit_upload)
                _show_result(output)
                if commit_upload and not output["error"]:
                    st.session_state["last_committed_session"] = SESSION_CODE
                    st.session_state["last_committed_date"]    = TODAY_STR

st.divider()

if (
    st.session_state.get("last_committed_session") == SESSION_CODE
    and st.session_state.get("last_committed_date") == TODAY_STR
):
    _show_absentee_section(TODAY_STR, SESSION_CODE)
    st.divider()

# Continuous session
st.markdown("## 🔄 Continuous Batch Session")
for k, v in [("continuous_running", False), ("last_capture_time", 0.0),
              ("continuous_result", None), ("capture_count", 0)]:
    if k not in st.session_state:
        st.session_state[k] = v

running = st.toggle("▶ Run continuous session", value=st.session_state["continuous_running"])
st.session_state["continuous_running"] = running

if running:
    now = time.time()
    elapsed = now - st.session_state["last_capture_time"]
    seconds_left = max(0, capture_interval - elapsed)
    st.success(f"🟢 Active · Capture #{st.session_state['capture_count']+1} in {int(seconds_left)}s")
    st.progress(1.0 - seconds_left / capture_interval, text=f"{int(seconds_left)}s remaining")
    if st.session_state["continuous_result"]:
        _show_result(st.session_state["continuous_result"])
    if elapsed >= capture_interval:
        with st.spinner("Auto-capturing…"):
            frame, err = _capture_webcam_frame(cam_source)
        if err:
            st.error(err, icon="🔴")
        else:
            with st.spinner("Processing…"):
                output = _run_batch(frame, known_students, commit=True)
            st.session_state["continuous_result"] = output
            st.session_state["capture_count"] += 1
            st.session_state["last_capture_time"] = time.time()
        time.sleep(0.5)
        st.rerun()
    else:
        time.sleep(min(seconds_left, 2.0))
        st.rerun()
else:
    if st.session_state["capture_count"] > 0:
        st.info(f"Session stopped after {st.session_state['capture_count']} capture(s).")
        st.session_state.update({"capture_count": 0, "last_capture_time": 0.0, "continuous_result": None})

st.divider()
st.caption(f"Batch mode · {session_label} · {TODAY_STR} · {len(known_students)} students · threshold {threshold:.2f}")
