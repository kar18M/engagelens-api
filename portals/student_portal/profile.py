"""
portals/student_portal/profile.py
====================================
Student Profile — Phase 10 (read-only).

Shows:
  - Name, roll no, class/section, enrollment date
  - Enrolled face photo thumbnails (front/left/right)
  - Parent Telegram link status
  - Overall attendance summary
"""

import streamlit as st
from pathlib import Path
import config

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

# ── Security guards ────────────────────────────────────────────────────────────
check_session_timeout()
require_role("student")
update_last_activity()

# Profile card styles inherited from global CSS (.profile-card, .field-label, .field-value)

user = get_current_user()
student_id = user.get("linked_student_id")
if not student_id:
    st.error("Account not linked to a student record. Contact admin.", icon="🚫")
    st.stop()

from database.db_operations import get_student_by_id
from database.mongo_client import get_db

student = get_student_by_id(student_id)
if not student:
    st.error("Student record not found. Contact admin.", icon="🚫")
    st.stop()

db = get_db()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("👤 My Profile")
st.caption("Read-only view of your enrollment details.")
st.divider()

# ── Profile info ───────────────────────────────────────────────────────────────
col_info, col_photo = st.columns([2, 1], gap="large")

with col_info:
    st.markdown('<div class="profile-card">', unsafe_allow_html=True)

    fields = [
        ("Student ID",    student_id),
        ("Full Name",     student.get("name", "—")),
        ("Roll Number",   student.get("roll_no", "—")),
        ("Class/Section", student.get("class_section", "—")),
        ("Enrolled On",   str(student.get("enrolled_on", "—"))[:10]),
    ]
    for label, value in fields:
        st.markdown(
            f"<div class='field-label'>{label}</div>"
            f"<div class='field-value'>{value}</div>",
            unsafe_allow_html=True,
        )

    # Telegram link status
    chat_id = student.get("parent_telegram_chat_id")
    st.markdown("<div class='field-label'>Parent Telegram</div>", unsafe_allow_html=True)
    if chat_id:
        st.success(f"✅ Linked (chat_id: `{chat_id}`)")
    else:
        st.warning("⏳ Not linked yet. Ask your teacher to share the Telegram link.")

    # Enrolled angles
    angles = [enc.get("angle", "?") for enc in student.get("face_encodings", [])]
    st.markdown("<div class='field-label' style='margin-top:8px'>Enrolled Angles</div>", unsafe_allow_html=True)
    angle_badge = {"front": "🟢 Front", "left_profile": "🔵 Left Profile", "right_profile": "🟣 Right Profile"}
    for ang in angles:
        st.markdown(f"- {angle_badge.get(ang, ang)}")

    st.markdown('</div>', unsafe_allow_html=True)

with col_photo:
    st.markdown("#### Enrolled Photos")
    enrolled_dir = config.ENROLLED_FACES_DIR / student_id
    if enrolled_dir.exists():
        for angle_name in ["front", "left_profile", "right_profile"]:
            for ext in ["jpg", "jpeg", "png"]:
                img_path = enrolled_dir / f"{angle_name}.{ext}"
                if img_path.exists():
                    st.image(
                        str(img_path),
                        caption=angle_name.replace("_", " ").title(),
                        use_container_width=True,
                    )
                    break
    else:
        st.info("No enrolled photos found.", icon="📷")

st.divider()

# ── Attendance summary ─────────────────────────────────────────────────────────
st.markdown("### 📊 All-Time Attendance Summary")
total = db["attendance"].count_documents({"student_id": student_id})
fn_count = db["attendance"].count_documents({"student_id": student_id, "session": "FN"})
an_count = db["attendance"].count_documents({"student_id": student_id, "session": "AN"})

c1, c2, c3 = st.columns(3)
c1.metric("Total Sessions Present", total)
c2.metric("Forenoon (FN)", fn_count)
c3.metric("Afternoon (AN)", an_count)

# Angle usage
st.markdown("##### Recognition Angle Breakdown")
import pandas as pd
pipeline = [
    {"$match": {"student_id": student_id}},
    {"$group": {"_id": "$matched_angle", "count": {"$sum": 1}}},
]
angle_data = list(db["attendance"].aggregate(pipeline))
if angle_data:
    angle_df = pd.DataFrame(angle_data).rename(columns={"_id": "Angle", "count": "Times Matched"})
    st.dataframe(angle_df, use_container_width=True, hide_index=True)

st.caption(f"EngageLens v2.0 · Student Portal · {student_id}")
