"""
pages/1_Live_Attendance.py
============================
Real-time webcam-based attendance for SMALL groups (study rooms, seminars).

NOTE: For a full classroom of 50–60 students, use "Batch Classroom Scan"
instead.  Live per-frame processing on CPU cannot keep pace with that many
simultaneous faces without significant frame drop.
"""

import streamlit as st

st.set_page_config(page_title="Live Attendance — EngageLens", page_icon="🎥", layout="wide")

st.title("🎥 Live Attendance")
st.caption("Real-time webcam mode · Best for small groups (< 15 students)")

st.warning(
    "**Large classrooms (50+ students):** Use the **📸 Batch Classroom Scan** page for "
    "best detection recall.  Live mode processes a reduced-resolution stream and will miss "
    "small/distant faces in a full classroom setting.",
    icon="⚠️",
)

# ── MongoDB & model checks ────────────────────────────────────────────────────
from database.mongo_client import get_db, MongoConnectionError

try:
    db = get_db()
except MongoConnectionError as e:
    st.error(str(e), icon="🔴")
    st.stop()

from database.db_operations import get_all_students, get_attendance_by_date
from datetime import date

enrolled_count = len(get_all_students())
if enrolled_count == 0:
    st.info(
        "No students enrolled yet.  Go to **🧑‍🎓 Enroll Student** to add students before starting live attendance.",
        icon="ℹ️",
    )
    st.stop()

# ── WebRTC live stream ─────────────────────────────────────────────────────────
try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
    from video_processor import VideoProcessor
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

col_stream, col_log = st.columns([3, 2], gap="large")

with col_stream:
    if not WEBRTC_AVAILABLE:
        st.error(
            "streamlit-webrtc is not installed.  "
            "Run: `pip install streamlit-webrtc av`",
            icon="🔴",
        )
    else:
        st.markdown("#### Live Camera Feed")

        RTC_CONFIG = RTCConfiguration(
            {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
        )

        ctx = webrtc_streamer(
            key="live-attendance",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIG,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        st.caption(
            f"Processing every {3}rd frame on CPU.  "
            f"{enrolled_count} student(s) in gallery."
        )

        # Threshold slider
        threshold = st.slider(
            "Recognition Threshold (cosine distance)",
            min_value=0.20, max_value=0.70, value=0.45, step=0.01,
            help="Lower = stricter matching (fewer false positives, more 'Unknown').  "
                 "Higher = more permissive (more matches, risk of false positives).",
        )

        if ctx.video_processor:
            ctx.video_processor.threshold = threshold
            if st.button("🔄 Reload Student Gallery"):
                ctx.video_processor.reload_gallery()
                st.success("Gallery reloaded from MongoDB.")

with col_log:
    st.markdown("#### Today's Attendance")
    today = date.today().isoformat()

    refresh = st.button("🔄 Refresh Log")

    records = get_attendance_by_date(today)

    if not records:
        st.info("No attendance marked yet today.")
    else:
        for rec in records:
            with st.container(border=True):
                st.markdown(f"**{rec['name']}** `{rec['student_id']}`")
                st.caption(
                    f"🕐 {rec.get('timestamp', '—')} · "
                    f"angle: {rec.get('matched_angle', '—')} · "
                    f"dist: {rec.get('match_distance', '—')}"
                )

    st.divider()
    if ctx and ctx.video_processor:
        live_log = ctx.video_processor.get_attendance_log()
        if live_log:
            st.markdown("**Session attendees (live)**")
            for sid, ts in live_log.items():
                st.markdown(f"- `{sid}` at {ts}")
