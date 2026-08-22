"""
portals/student_portal/dashboard.py
=====================================
Student Dashboard — Phase 10.

Shows:
  - Big attendance % ring chart (Plotly donut)
  - Present / Absent / Total session counts this month
  - Warning banner if below ATTENDANCE_WARNING_THRESHOLD
  - FN/AN breakdown for today
  - Quick recent history (last 7 days)

Theme: Soft blue-green, large numbers, single-column, mobile-friendly.
"""

import streamlit as st
from datetime import date, timedelta
from calendar import monthrange
import plotly.graph_objects as go
import pandas as pd

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

# ── Security guards ────────────────────────────────────────────────────────────
check_session_timeout()
require_role("student")
update_last_activity()

# ── Student portal CSS ─────────────────────────────────────────────────────────
# Stat colours inherited from global CSS (--dark, --muted, --subtle)


# ── Load student data ──────────────────────────────────────────────────────────
user = get_current_user()
student_id = user.get("linked_student_id")

if not student_id:
    st.error("⚠️ Your account is not linked to a student record. Contact admin.", icon="🚫")
    st.stop()

from database.db_operations import get_student_by_id, get_all_attendance
from database.mongo_client import get_db
import config

student = get_student_by_id(student_id)
if not student:
    st.error(f"Student record for ID `{student_id}` not found. Contact admin.", icon="🚫")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
st.title(f"🏠 My Dashboard")
st.markdown(
    f"<div style='font-size:1rem;color:#6B6B6B;margin-bottom:8px;font-weight:500'>"
    f"Welcome back, <b style='color:#1A1A1A'>{student['name']}</b> &nbsp;·&nbsp; "
    f"{student.get('roll_no','—')} &nbsp;·&nbsp; {student.get('class_section','—')}"
    f"</div>",
    unsafe_allow_html=True,
)
st.divider()

# ── Fetch this student's attendance ───────────────────────────────────────────
db = get_db()
all_records = list(db["attendance"].find({"student_id": student_id}, {"_id": 0}))

today = date.today()
month_start = today.replace(day=1)

# ── This-month stats ──────────────────────────────────────────────────────────
this_month_records = [
    r for r in all_records
    if r.get("date", "") >= month_start.isoformat()
]

present_count = len(this_month_records)

# Compute total expected sessions this month (each weekday = 2 sessions FN+AN)
# Simple approximation: days elapsed × 2
days_elapsed   = (today - month_start).days + 1
# Only count Mon-Fri
total_sessions = sum(
    1 for d in range(days_elapsed)
    if (month_start + timedelta(days=d)).weekday() < 5
) * 2

absent_count = max(0, total_sessions - present_count)
attendance_pct = (present_count / total_sessions * 100) if total_sessions > 0 else 0

# ── Warning banner ────────────────────────────────────────────────────────────
if total_sessions > 0 and attendance_pct < config.ATTENDANCE_WARNING_THRESHOLD:
    st.markdown(
        f"""<div class="warn-banner">
          ⚠️ <b>Attendance Warning</b><br>
          Your attendance this month is <b style="color:#991B1B">{attendance_pct:.1f}%</b>,
          which is below the required <b>{config.ATTENDANCE_WARNING_THRESHOLD}%</b> threshold.
          Please contact your class in-charge.
        </div>""",
        unsafe_allow_html=True,
    )

# ── Ring chart ─────────────────────────────────────────────────────────────────
col_chart, col_stats = st.columns([1, 1], gap="large")

with col_chart:
    st.markdown("### This Month's Attendance")

    fig = go.Figure(go.Pie(
        values=[max(present_count, 0), max(absent_count, 0)],
        labels=["Present", "Absent"],
        hole=0.74,
        marker_colors=["#1A1A1A", "#EBEBEA"],
        textinfo="none",
        hovertemplate="%{label}: %{value} sessions<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{attendance_pct:.0f}%</b>",
        x=0.5, y=0.5,
        font=dict(size=38, color="#1A1A1A", family="Outfit"),
        showarrow=False,
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", y=-0.1, x=0.5, xanchor="center",
            font=dict(family="Outfit", size=12, color="#6B6B6B"),
        ),
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

with col_stats:
    st.markdown("### Month Summary")
    month_name = today.strftime("%B %Y")
    st.caption(f"📅 {month_name}")

    st.markdown(
        f"""
        <div class="stat-card" style="margin-bottom:12px">
            <div class="stat-number present-num">{present_count}</div>
            <div class="stat-label">Sessions Present</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-card" style="margin-bottom:12px">
            <div class="stat-number absent-num">{absent_count}</div>
            <div class="stat-label">Sessions Absent</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-number total-num">{total_sessions}</div>
            <div class="stat-label">Total Sessions (est.)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Today's status ─────────────────────────────────────────────────────────────
st.markdown("### Today's Status")
today_str = today.isoformat()
today_records = [r for r in all_records if r.get("date") == today_str]
today_sessions = {r.get("session"): r for r in today_records}

c_fn, c_an = st.columns(2)
with c_fn:
    fn_rec = today_sessions.get("FN")
    if fn_rec:
        st.success(
            f"✅ **Forenoon (FN)** — Present\n\n"
            f"Matched at `{fn_rec.get('timestamp','—')}` · angle: `{fn_rec.get('matched_angle','—')}`",
        )
    else:
        st.error("❌ **Forenoon (FN)** — Not marked present")

with c_an:
    an_rec = today_sessions.get("AN")
    if an_rec:
        st.success(
            f"✅ **Afternoon (AN)** — Present\n\n"
            f"Matched at `{an_rec.get('timestamp','—')}` · angle: `{an_rec.get('matched_angle','—')}`",
        )
    else:
        st.error("❌ **Afternoon (AN)** — Not marked present")

st.divider()

# ── Recent 7-day history ───────────────────────────────────────────────────────
st.markdown("### Last 7 Days")
week_ago = (today - timedelta(days=6)).isoformat()
recent = sorted(
    [r for r in all_records if r.get("date", "") >= week_ago],
    key=lambda r: (r.get("date",""), r.get("session","")),
    reverse=True,
)

if not recent:
    st.info("No attendance records in the last 7 days.", icon="📅")
else:
    df = pd.DataFrame(recent)[["date", "session", "status", "matched_angle", "match_distance"]]
    df.columns = ["Date", "Session", "Status", "Matched Angle", "Distance"]
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption(
    f"EngageLens v2.0 · Student Portal · {student_id} · "
    f"Data refreshes on every page load"
)
