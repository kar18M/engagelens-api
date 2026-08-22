"""
portals/teacher_portal/class_overview.py
==========================================
Teacher — Class Overview Page (Phase 10).

Shows all students in the teacher's assigned_sections with today's
FN/AN attendance status. Sortable, searchable. Dense, data-table-first UI.
"""

import streamlit as st
import pandas as pd
from datetime import date

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

# ── Security guards ────────────────────────────────────────────────────────────
check_session_timeout()
require_role("teacher", "admin")
update_last_activity()



user = get_current_user()
assigned_sections = user.get("assigned_sections", [])
role = user.get("role")

from database.mongo_client import get_db
from database.db_operations import get_all_students, get_attendance_by_date, get_absentees

db = get_db()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📋 Class Overview")

# Show sections this teacher is assigned to
if role == "admin":
    st.caption("Admin view — all sections")
else:
    if assigned_sections:
        chips = " ".join(
            f'<span class="section-chip">{s}</span>' for s in assigned_sections
        )
        st.markdown(f"Your sections: {chips}", unsafe_allow_html=True)
    else:
        st.warning(
            "⚠️ No sections assigned to your account. "
            "Contact admin to assign you to one or more class sections.",
            icon="⚠️",
        )
        st.stop()

st.divider()

# ── Session + Date controls ────────────────────────────────────────────────────
col_d, col_s = st.columns([2, 2])
today = date.today()
with col_d:
    selected_date = st.date_input("Date", value=today, max_value=today, key="ov_date")
with col_s:
    session_sel = st.radio("Session", ["FN", "AN", "Both"], horizontal=True, key="ov_sess")

date_str = selected_date.isoformat()

# ── Fetch students scoped to this teacher's sections ──────────────────────────
if role == "admin":
    query = {}   # Admin sees all
else:
    query = {"class_section": {"$in": assigned_sections}}

all_students = list(db["students"].find(query, {"_id": 0, "face_encodings": 0}))

if not all_students:
    st.info(
        "No enrolled students found in your assigned sections.",
        icon="ℹ️",
    )
    st.stop()

# ── Get present sets ───────────────────────────────────────────────────────────
from database.db_operations import get_present_student_ids
fn_present = get_present_student_ids(date_str, "FN") if session_sel in ["FN", "Both"] else set()
an_present = get_present_student_ids(date_str, "AN") if session_sel in ["AN", "Both"] else set()

# ── Search filter ──────────────────────────────────────────────────────────────
search = st.text_input("🔍 Search by name or roll no", placeholder="Type to filter…", key="ov_search")

# ── Build display table ────────────────────────────────────────────────────────
rows = []
for stu in all_students:
    sid  = stu["student_id"]
    name = stu.get("name", sid)
    roll = stu.get("roll_no", sid)
    sec  = stu.get("class_section", "—")

    fn_status = "✅ Present" if sid in fn_present else "❌ Absent"
    an_status = "✅ Present" if sid in an_present else "❌ Absent"

    row: dict = {
        "Name":          name,
        "Roll No":       roll,
        "Section":       sec,
    }
    if session_sel in ["FN", "Both"]:
        row["FN Status"] = fn_status
    if session_sel in ["AN", "Both"]:
        row["AN Status"] = an_status

    rows.append(row)

df = pd.DataFrame(rows)

# Apply search filter
if search:
    mask = (
        df["Name"].str.contains(search, case=False, na=False) |
        df["Roll No"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

# ── Metrics row ────────────────────────────────────────────────────────────────
total_stu = len(all_students)
if session_sel == "FN":
    present_n = sum(1 for s in all_students if s["student_id"] in fn_present)
elif session_sel == "AN":
    present_n = sum(1 for s in all_students if s["student_id"] in an_present)
else:
    present_n = sum(
        1 for s in all_students
        if s["student_id"] in fn_present or s["student_id"] in an_present
    )

c1, c2, c3 = st.columns(3)
c1.metric("Total Students", total_stu)
c2.metric("Present", present_n)
c3.metric("Absent / Unknown", total_stu - present_n)

st.markdown(f"##### Showing **{len(df)}** of **{total_stu}** students — `{date_str}` · `{session_sel}` session")

# ── Table ──────────────────────────────────────────────────────────────────────
st.dataframe(df, use_container_width=True, hide_index=True, height=400)

# ── CSV export ─────────────────────────────────────────────────────────────────
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Export CSV",
    data=csv,
    file_name=f"class_overview_{date_str}_{session_sel}.csv",
    mime="text/csv",
)

st.caption(f"EngageLens v2.0 · Teacher Portal · {user.get('full_name','')}")
