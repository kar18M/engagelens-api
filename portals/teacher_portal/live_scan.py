"""
portals/teacher_portal/live_scan.py
=====================================
Teacher — Live Attendance (Phase 10).
Ported from pages/1_Live_Attendance.py with role guard added.
"""

import streamlit as st
from datetime import date

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("teacher", "admin")
update_last_activity()



from database.mongo_client import get_db, MongoConnectionError
from database.db_operations import get_all_students, get_attendance_by_date

st.title("🎥 Live Attendance")
st.caption("Real-time webcam mode · Best for small groups (< 15 students)")

st.warning(
    "**Large classrooms (50+ students):** Use **Batch Scan** for best recall. "
    "Live mode processes a reduced-resolution stream and may miss small/distant faces.",
    icon="⚠️",
)

enrolled_count = len(get_all_students())
if enrolled_count == 0:
    st.info("No students enrolled yet. Go to **Enroll Student** to add students.", icon="ℹ️")
    st.stop()

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
    from video_processor import VideoProcessor
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

col_stream, col_log = st.columns([3, 2], gap="large")

with col_stream:
    if not WEBRTC_AVAILABLE:
        st.error("streamlit-webrtc is not installed. Run: `pip install streamlit-webrtc av`", icon="🔴")
    else:
        st.markdown("#### Live Camera Feed")
        RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        ctx = webrtc_streamer(
            key="live-attendance-teacher",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIG,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )
        st.caption(f"Processing every 3rd frame · {enrolled_count} student(s) in gallery.")

        threshold = st.slider("Recognition Threshold", 0.20, 0.70, 0.45, 0.01)
        if ctx.video_processor:
            ctx.video_processor.threshold = threshold
            if st.button("🔄 Reload Gallery"):
                ctx.video_processor.reload_gallery()
                st.success("Gallery reloaded.")

with col_log:
    st.markdown("#### Today's Attendance")
    today = date.today().isoformat()
    st.button("🔄 Refresh Log")
    records = get_attendance_by_date(today)
    if not records:
        st.info("No attendance marked yet today.")
    else:
        for rec in records:
            with st.container(border=True):
                st.markdown(f"**{rec['name']}** `{rec['student_id']}`")
                st.caption(
                    f"🕐 {rec.get('timestamp','—')} · "
                    f"angle: {rec.get('matched_angle','—')} · "
                    f"dist: {rec.get('match_distance','—')}"
                )

    if WEBRTC_AVAILABLE and ctx and ctx.video_processor:
        live_log = ctx.video_processor.get_attendance_log()
        if live_log:
            st.divider()
            st.markdown("**Session attendees (live)**")
            for sid, ts in live_log.items():
                st.markdown(f"- `{sid}` at {ts}")
