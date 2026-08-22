"""
pages/2_Batch_Classroom_Scan.py
=================================
Batch Attendance Mode — designed for large classrooms (30–60+ students).

Phase 9 additions:
  • Session selector (FN / AN) at the top — required before running a scan.
  • After attendance is committed, absentee section computes who was NOT marked
    present in this session and lets the teacher send Telegram alerts with
    one click.
  • "Alerts already sent" guard prevents duplicate messages.
"""

import time
from datetime import date

import cv2
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Batch Attendance — EngageLens",
    page_icon="🎬",
    layout="wide",
)

# ── DB / model check ──────────────────────────────────────────────────────────
from database.mongo_client import get_db, MongoConnectionError

try:
    get_db()
except MongoConnectionError as e:
    st.error(str(e), icon="🔴")
    st.stop()

from database.db_operations import (
    get_all_students,
    mark_attendance_if_new,
    get_absentees,
    get_notification_log,
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

# ── Sidebar settings ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Batch Settings")

    capture_interval = st.slider(
        "Capture interval (seconds)",
        min_value=5, max_value=120, value=30, step=5,
        help="How often the continuous session auto-captures a snapshot.",
    )

    upscale_factor = st.slider(
        "Tile upscale factor",
        min_value=1, max_value=4, value=2, step=1,
        help="Upscale webcam frame before tiling.  Higher = more pixels for the detector = better recall for small faces, but slower.",
    )

    threshold = st.slider(
        "Recognition threshold",
        min_value=0.20, max_value=0.70, value=0.55, step=0.01,
        help="Cosine distance cutoff. Lower = stricter.",
    )

    st.divider()
    tile_size = _cfg.TILE_SIZE
    overlap   = _cfg.TILE_OVERLAP
    min_face  = _cfg.MIN_FACE_SIZE_PX
    st.caption(f"Tile size: {tile_size}×{tile_size} px")
    st.caption(f"Overlap: {int(overlap / tile_size * 100)} %")
    st.caption(f"Min face: {min_face} px")

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🎬 Batch Attendance Mode")
st.markdown(
    "Designed for **large classrooms (30–60+ students)** seated in rows.  "
    "Instead of a continuous video stream, this mode captures periodic "
    "high-resolution snapshots and processes each one thoroughly."
)

st.info(
    "**🎬 Batch mode trade-off:** Each capture may take 3–15 seconds depending "
    "on face count and hardware.  It is optimised for *accuracy* across a full "
    "classroom, not for real-time display.  \n\n"
    "**Live mode** is faster but only reliable for ≤ 10 people in frame.  "
    "Use Batch mode for lectures, exams, or any scene with many students.",
    icon="ℹ️",
)

st.divider()

# ── Session Selector (Phase 9) ────────────────────────────────────────────────
st.markdown("### 📅 Session")
session_label = st.radio(
    "Select session for this scan:",
    options=["Forenoon (FN)", "Afternoon (AN)"],
    horizontal=True,
    key="session_radio",
    help="Attendance records are tracked separately for Forenoon (FN) and Afternoon (AN) sessions.",
)
SESSION_CODE = "FN" if "FN" in session_label else "AN"
TODAY_STR = date.today().isoformat()

st.caption(
    f"📌 Recording attendance for **{session_label}** session on **{TODAY_STR}**"
)

st.divider()

# ── Helper: decode an st.camera_input() image to a BGR frame ─────────────────
def _camera_input_to_bgr(uploaded_img) -> tuple[np.ndarray | None, str | None]:
    """
    Convert the bytes returned by st.camera_input() into an OpenCV BGR frame.
    Returns (bgr_frame, error_message).
    """
    file_bytes = np.frombuffer(uploaded_img.getvalue(), np.uint8)
    frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if frame is None:
        return None, "Could not decode the captured image. Please try again."
    return frame, None


# ── Helper: run full batch pipeline on a BGR frame ────────────────────────────
def _run_batch(frame: np.ndarray, known_students: list, commit: bool = True) -> dict:
    """
    Optionally upscale the frame, then run the tiling batch pipeline.
    Returns the output dict from batch_processor.process_classroom_image().
    """
    if upscale_factor > 1:
        h, w = frame.shape[:2]
        frame = cv2.resize(
            frame,
            (w * upscale_factor, h * upscale_factor),
            interpolation=cv2.INTER_CUBIC,
        )

    return batch_processor.process_classroom_image(
        image_source=frame,
        known_students=known_students,
        threshold=threshold,
        commit_attendance=commit,
        session=SESSION_CODE,
    )


# ── Helper: display batch result ──────────────────────────────────────────────
def _show_result(output: dict):
    if output["error"]:
        st.error(output["error"], icon="⚠️")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("👤 Detected",    output["n_detected"])
    c2.metric("✅ Recognised",  output["n_recognised"])
    c3.metric("❓ Unknown",     output["n_unknown"])

    if output["annotated_image"] is not None:
        st.image(
            cv2.cvtColor(output["annotated_image"], cv2.COLOR_BGR2RGB),
            caption="Detection + Recognition Results",
            use_container_width=True,
        )

    newly = output.get("attendance_new", [])
    if newly:
        st.success(f"Attendance marked for {len(newly)} new student(s): {', '.join(newly)}", icon="✅")
    elif output["n_recognised"] > 0:
        st.info("All recognised students were already marked present for this session.", icon="ℹ️")


# ── Helper: absentee alert section ────────────────────────────────────────────
def _show_absentee_section(date_str: str, session: str):
    """
    Shown after the teacher commits attendance for a session.
    Computes absentees, shows the table, and provides the Send Alerts button.
    """
    st.markdown(f"---\n### 📢 Absentee Alerts — {session} Session")

    with st.spinner("Computing absentees…"):
        absentees = get_absentees(date_str, session)

    if not absentees:
        st.success(
            "All enrolled students were marked present for this session. No alerts needed.",
            icon="✅",
        )
        return

    st.warning(
        f"**{len(absentees)} absentee(s)** found for the {session} session on {date_str}.",
        icon="⚠️",
    )

    # ── Build display table ────────────────────────────────────────────────────
    import pandas as pd

    rows = []
    all_already_sent = True
    for s in absentees:
        log = get_notification_log(s["student_id"], date_str, session)
        if log and log.get("status") == "sent":
            alert_status = "✅ Sent"
        elif log and log.get("status") == "failed":
            alert_status = "❌ Failed"
            all_already_sent = False
        elif log and log.get("status") == "skipped_no_chat_id":
            alert_status = "⚠️ No parent linked"
        else:
            alert_status = "⏳ Pending"
            all_already_sent = False

        rows.append({
            "Name":           s["name"],
            "Roll No":        s["roll_no"],
            "Class/Section":  s["class_section"],
            "Parent Linked":  "✅ Yes" if s.get("parent_telegram_chat_id") else "❌ No",
            "Alert Status":   alert_status,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Send Alerts button ────────────────────────────────────────────────────
    if all_already_sent:
        st.success(
            "All absentee alerts have already been sent for this session.",
            icon="✅",
        )
        st.button(
            "📨 Alerts Already Sent",
            disabled=True,
            key="send_alerts_btn_done",
            use_container_width=True,
        )
    else:
        bot_configured = bool(_cfg.TELEGRAM_BOT_TOKEN)
        if not bot_configured:
            st.warning(
                "⚠️ `TELEGRAM_BOT_TOKEN` is not set. "
                "Set the environment variable and restart the app to enable alerts.",
                icon="⚠️",
            )

        if st.button(
            f"📨 Send Absentee Alerts ({len(absentees)} student(s))",
            type="primary",
            key="send_alerts_btn",
            use_container_width=True,
            disabled=not bot_configured,
        ):
            with st.spinner("Sending Telegram alerts…"):
                results = send_batch_alerts(absentees, date_str, session)

            st.markdown("#### Alert Results")
            for r in results:
                student_name = next(
                    (s["name"] for s in absentees if s["student_id"] == r["student_id"]),
                    r["student_id"],
                )
                status = r["status"]
                if status == "sent":
                    st.success(f"✅ **{student_name}** — Alert sent (msg_id: {r['telegram_message_id']})", icon="✅")
                elif status == "already_sent":
                    st.info(f"⏭️ **{student_name}** — Already sent previously", icon="ℹ️")
                elif status == "skipped_no_chat_id":
                    st.warning(f"⚠️ **{student_name}** — No parent Telegram linked", icon="⚠️")
                elif status == "failed":
                    err = r.get("error", "Unknown error")
                    st.error(f"❌ **{student_name}** — Failed: {err}", icon="❌")

            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Load gallery (cached per session)
# ─────────────────────────────────────────────────────────────────────────────
if "known_students" not in st.session_state:
    st.session_state["known_students"] = load_known_students()

known_students = st.session_state["known_students"]

if not known_students:
    st.warning(
        "No students enrolled yet.  "
        "Go to **🧑‍🎓 Enroll Student** first, then return here to scan.",
        icon="⚠️",
    )

col_reload = st.columns([8, 2])[1]
if col_reload.button("🔄 Reload Gallery"):
    st.session_state["known_students"] = load_known_students()
    st.success(f"Gallery reloaded — {len(st.session_state['known_students'])} student(s).")
    st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Webcam Capture / Upload Photo tabs
# ─────────────────────────────────────────────────────────────────────────────
tab_webcam, tab_upload = st.tabs(["📷 Webcam Capture", "🖼️ Upload Photo"])

# Initialise session state for tracking last committed scan
if "last_committed_session" not in st.session_state:
    st.session_state["last_committed_session"] = None
if "last_committed_date" not in st.session_state:
    st.session_state["last_committed_date"] = None

# ── TAB: Webcam Capture ───────────────────────────────────────────────────────
with tab_webcam:
    st.markdown(
        "Point your **device's camera** at the classroom and click the capture "
        "button below. The photo is taken directly from **your device** — works on "
        "any phone, tablet, or laptop that opens this page."
    )
    st.divider()

    # st.camera_input uses the browser's WebRTC API — always captures from the
    # device that is viewing the page, regardless of where the server is running.
    camera_photo = st.camera_input(
        "📷 Capture classroom photo",
        key="batch_camera_input",
        help="Allow camera access in your browser when prompted.",
    )

    if camera_photo is not None:
        frame, err = _camera_input_to_bgr(camera_photo)

        if err:
            st.error(err, icon="🔴")
        else:
            st.success("Snapshot captured — running batch pipeline…", icon="📷")
            with st.spinner("Tiling → detecting → recognising…"):
                output = _run_batch(frame, known_students, commit=True)
            _show_result(output)
            if not output["error"]:
                # Record that attendance was committed for this session
                st.session_state["last_committed_session"] = SESSION_CODE
                st.session_state["last_committed_date"]    = TODAY_STR

# ── TAB: Upload Photo ─────────────────────────────────────────────────────────
with tab_upload:
    st.markdown(
        "Upload a classroom photo (JPEG/PNG) to test batch processing without "
        "needing a live camera — useful for demos or testing."
    )
    st.divider()

    uploaded = st.file_uploader(
        "Upload classroom photo",
        type=["jpg", "jpeg", "png", "webp"],
        key="batch_upload",
    )

    if uploaded:
        file_bytes = np.frombuffer(uploaded.read(), np.uint8)
        image_bgr  = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if image_bgr is None:
            st.error("Could not decode the image. Please upload a valid JPEG or PNG.", icon="❌")
        else:
            h, w = image_bgr.shape[:2]
            st.caption(f"Image: {uploaded.name} · {w}×{h} px")

            commit_upload = st.checkbox("Commit attendance after processing", value=True, key="upload_commit")

            if st.button("▶️ Process Image", type="primary", key="process_upload_btn"):
                with st.spinner("Tiling → detecting → recognising…"):
                    output = _run_batch(image_bgr, known_students, commit=commit_upload)
                _show_result(output)
                if commit_upload and not output["error"]:
                    st.session_state["last_committed_session"] = SESSION_CODE
                    st.session_state["last_committed_date"]    = TODAY_STR

st.divider()

# ── Absentee Alerts section (shown after any committed scan) ──────────────────
if (
    st.session_state.get("last_committed_session") == SESSION_CODE
    and st.session_state.get("last_committed_date") == TODAY_STR
):
    _show_absentee_section(TODAY_STR, SESSION_CODE)
    st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Continuous Batch Session
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## 🔄 Continuous Batch Session")
st.info(
    "**Continuous mode** uses the same browser-based camera as the single-capture tab above.  "
    "Keep the **📷 Webcam Capture** tab open on your device and retake the photo every "
    f"**{capture_interval}s** using the camera widget.  "
    "Each new photo will be detected and processed automatically once captured.",
    icon="ℹ️",
)

st.divider()
st.caption(
    f"Batch mode · {session_label} · {TODAY_STR} · "
    f"{len(known_students)} student(s) in gallery · "
    f"Threshold: {threshold:.2f} · Upscale: {upscale_factor}×"
)
