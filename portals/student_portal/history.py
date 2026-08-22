"""
portals/student_portal/history.py
====================================
Student Attendance History — Phase 10.

Features:
  - Date range filter
  - FN/AN session breakdown table
  - Calendar heatmap (green=present, red=absent, grey=no session)
  - CSV download
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import io

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

# ── Security guards ────────────────────────────────────────────────────────────
check_session_timeout()
require_role("student")
update_last_activity()


user = get_current_user()
student_id = user.get("linked_student_id")
if not student_id:
    st.error("Account not linked to a student record. Contact admin.", icon="🚫")
    st.stop()

from database.mongo_client import get_db
from database.db_operations import get_student_by_id

student = get_student_by_id(student_id)
if not student:
    st.error("Student record not found.", icon="🚫")
    st.stop()

db = get_db()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📅 My Attendance History")
st.caption(f"{student['name']} · {student.get('roll_no','—')} · {student.get('class_section','—')}")
st.divider()

# ── Date range filter ──────────────────────────────────────────────────────────
today = date.today()
col_f1, col_f2, col_f3 = st.columns([2, 2, 1])

with col_f1:
    date_from = st.date_input(
        "From",
        value=today.replace(day=1),
        max_value=today,
        key="hist_from",
    )
with col_f2:
    date_to = st.date_input(
        "To",
        value=today,
        max_value=today,
        key="hist_to",
    )
with col_f3:
    session_f = st.radio("Session", ["Both", "FN", "AN"], horizontal=False, key="hist_sess")

if date_from > date_to:
    st.error("'From' date must be before 'To' date.", icon="❌")
    st.stop()

# ── Query records ──────────────────────────────────────────────────────────────
query = {
    "student_id": student_id,
    "date": {"$gte": date_from.isoformat(), "$lte": date_to.isoformat()},
}
if session_f != "Both":
    query["session"] = session_f

records = list(db["attendance"].find(query, {"_id": 0}).sort("date", -1))

st.markdown(f"**{len(records)} record(s)** from `{date_from}` to `{date_to}`")

# ── Records table ──────────────────────────────────────────────────────────────
if records:
    df = pd.DataFrame(records)
    disp_cols = ["date", "session", "status", "matched_angle", "match_distance"]
    disp_cols = [c for c in disp_cols if c in df.columns]
    df_disp = df[disp_cols].rename(columns={
        "date": "Date", "session": "Session", "status": "Status",
        "matched_angle": "Matched Angle", "match_distance": "Distance",
    })
    st.dataframe(df_disp, use_container_width=True, hide_index=True)

    # ── CSV download ───────────────────────────────────────────────────────────
    csv_bytes = df_disp.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download as CSV",
        data=csv_bytes,
        file_name=f"attendance_{student_id}_{date_from}_{date_to}.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("No attendance records found for this date range.", icon="📅")

st.divider()

# ── Calendar heatmap ───────────────────────────────────────────────────────────
st.markdown("### 📆 Attendance Calendar")
st.caption("🟢 Present  🔴 Absent (expected session)  ⬜ No session")

# Fetch all records (no date filter) for calendar
all_records = list(db["attendance"].find({"student_id": student_id}, {"_id": 0, "date": 1, "session": 1}))
present_keys = {(r["date"], r.get("session", "")) for r in all_records}

# Build a dataframe of dates for the past 60 days × 2 sessions
end_date   = today
start_date = today - timedelta(days=59)

rows = []
d = start_date
while d <= end_date:
    for sess in ["FN", "AN"]:
        key = (d.isoformat(), sess)
        if d.weekday() < 5:  # Mon–Fri = expected session
            status = "Present" if key in present_keys else "Absent"
        else:
            status = "No session"
        rows.append({"Date": d.isoformat(), "Session": sess, "Status": status})
    d += timedelta(days=1)

cal_df = pd.DataFrame(rows)

# Pivot: rows=Session, cols=Date
pivot = cal_df.pivot(index="Session", columns="Date", values="Status")
color_map = {"Present": 1, "Absent": -1, "No session": 0}
z = pivot.applymap(lambda x: color_map.get(x, 0))

fig = go.Figure(go.Heatmap(
    z=z.values,
    x=list(pivot.columns),
    y=list(pivot.index),
    colorscale=[
        [0.0, "#E5E5E3"],
        [0.5, "#D0D0CE"],
        [1.0, "#1A1A1A"],
    ],
    zmin=-1, zmax=1,
    showscale=False,
    hovertemplate="Date: %{x}<br>Session: %{y}<br>Status: %{customdata}<extra></extra>",
    customdata=pivot.values,
    xgap=2, ygap=2,
))
fig.update_layout(
    margin=dict(t=20, b=60, l=60, r=20),
    height=160,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False, tickangle=-45, tickfont=dict(size=9)),
    yaxis=dict(showgrid=False),
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Calendar shows last 60 days (Mon–Fri sessions only). "
    f"EngageLens v2.0 · Student Portal"
)
