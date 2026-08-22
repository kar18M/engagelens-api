"""
portals/teacher_portal/override.py
=====================================
Teacher — Manual Attendance Override (Phase 10).

Allows teachers to manually mark a student Present or Absent
for a specific date and session. Every change writes to:
  - attendance collection (upsert)
  - audit_log collection

Security:
  - Teacher can only override students in their assigned_sections (DB-level filter).
  - Admin can override any student.
  - Remark field is mandatory.
"""

import streamlit as st
from datetime import date, timedelta

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

# ── Security guards ────────────────────────────────────────────────────────────
check_session_timeout()
require_role("teacher", "admin")
update_last_activity()

# Override card styles inherited from global CSS (.override-card)


user = get_current_user()
assigned_sections = user.get("assigned_sections", [])
role = user.get("role")
actor_user_id = user.get("user_id", "unknown")

from database.mongo_client import get_db
from auth.user_operations import log_audit
from datetime import datetime

db = get_db()

st.title("✏️ Override Attendance")
st.caption(
    "Manually mark a student Present or Absent for a specific date and session. "
    "All changes are logged in the audit trail."
)
st.divider()

# ── Fetch scoped students ──────────────────────────────────────────────────────
if role == "admin":
    query = {}
else:
    if not assigned_sections:
        st.warning("No sections assigned. Contact admin.", icon="⚠️")
        st.stop()
    query = {"class_section": {"$in": assigned_sections}}

students = list(db["students"].find(query, {"_id": 0, "face_encodings": 0}))
if not students:
    st.info("No students found in your assigned sections.", icon="ℹ️")
    st.stop()

# Build select options
student_options = {
    f"{s['name']} ({s.get('roll_no', s['student_id'])}) — {s.get('class_section','?')}": s["student_id"]
    for s in sorted(students, key=lambda x: x.get("name",""))
}

# ── Override form ──────────────────────────────────────────────────────────────
with st.form("override_form", clear_on_submit=True):
    st.markdown("### Override Details")

    selected_label = st.selectbox(
        "Select Student *",
        options=list(student_options.keys()),
        key="ov_student_select",
    )

    col1, col2 = st.columns(2)
    with col1:
        ov_date = st.date_input(
            "Date *",
            value=date.today(),
            max_value=date.today(),
            min_value=date.today() - timedelta(days=90),
            key="ov_date_input",
        )
    with col2:
        ov_session = st.radio("Session *", ["FN", "AN"], horizontal=True, key="ov_session_input")

    new_status = st.radio(
        "Mark as *",
        ["Present", "Absent"],
        horizontal=True,
        key="ov_status_input",
    )

    remark = st.text_input(
        "Remark * (mandatory — e.g. 'Medical leave', 'Correction')",
        placeholder="Enter reason for override…",
        key="ov_remark_input",
    )

    submitted = st.form_submit_button(
        "💾 Save Override",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if not remark.strip():
        st.error("Remark is mandatory. Please explain the reason for this override.", icon="❌")
    else:
        student_id = student_options[selected_label]
        date_str   = ov_date.isoformat()
        session    = ov_session

        # ── Fetch student details ──────────────────────────────────────────────
        stu_doc = next((s for s in students if s["student_id"] == student_id), {})
        name    = stu_doc.get("name", student_id)
        roll_no = stu_doc.get("roll_no", student_id)
        section = stu_doc.get("class_section", "")

        # ── Read current status for audit ──────────────────────────────────────
        existing = db["attendance"].find_one(
            {"student_id": student_id, "date": date_str, "session": session},
            {"_id": 0, "status": 1},
        )
        old_status = existing["status"] if existing else "Absent (no record)"

        with st.spinner("Saving override…"):
            if new_status == "Present":
                # Upsert a Present record
                db["attendance"].update_one(
                    {"student_id": student_id, "date": date_str, "session": session},
                    {"$set": {
                        "student_id":    student_id,
                        "name":          name,
                        "roll_no":       roll_no,
                        "class_section": section,
                        "date":          date_str,
                        "session":       session,
                        "timestamp":     datetime.utcnow().strftime("%H:%M:%S"),
                        "status":        "Present",
                        "matched_angle": "manual_override",
                        "match_distance": 0.0,
                        "remark":        remark.strip(),
                        "overridden_by": actor_user_id,
                    }},
                    upsert=True,
                )
            else:
                # Delete the attendance record (marks as absent)
                db["attendance"].delete_one(
                    {"student_id": student_id, "date": date_str, "session": session}
                )

        # ── Write audit log ────────────────────────────────────────────────────
        log_audit(
            actor_user_id=actor_user_id,
            actor_role=role,
            action="attendance_override",
            target=f"student_id={student_id}, date={date_str}, session={session}",
            old_value=old_status,
            new_value=f"{new_status} (remark: {remark.strip()})",
        )

        st.success(
            f"✅ Override saved: **{name}** ({session} · {date_str}) → **{new_status}**\n\n"
            f"Remark: _{remark.strip()}_",
            icon="✅",
        )

st.divider()

# ── Recent overrides ───────────────────────────────────────────────────────────
st.markdown("### Recent Overrides (Audit Log)")
from auth.user_operations import get_audit_log
recent = get_audit_log(action="attendance_override", limit=20)

if not recent:
    st.info("No overrides recorded yet.", icon="📋")
else:
    import pandas as pd
    df = pd.DataFrame(recent)[["timestamp", "actor_user_id", "target", "old_value", "new_value"]]
    df.columns = ["Time", "Actor", "Target", "Before", "After"]
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption(f"EngageLens v2.0 · Teacher Portal · {user.get('full_name','')}")
