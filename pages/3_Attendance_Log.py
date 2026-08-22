"""
pages/3_Attendance_Log.py
===========================
View, filter, and export attendance records.
Includes matched_angle and match_distance columns for recognition quality
transparency.

Phase 9 additions:
  - Session filter: FN / AN / Both
  - session column in the table
  - alert_sent column (Yes / No / N/A) — Present students never receive alerts
  - Updated CSV download includes new columns
"""

import io
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Attendance Log — EngageLens",
    page_icon="📋",
    layout="wide",
)

# ── DB check ──────────────────────────────────────────────────────────────────
from database.mongo_client import get_db, MongoConnectionError

try:
    get_db()
except MongoConnectionError as e:
    st.error(str(e), icon="🔴")
    st.stop()

from database.db_operations import (
    get_attendance_by_date,
    get_attendance_stats,
    get_all_attendance,
    get_notification_log,
    get_absentees,
)
from notifications.telegram_bot import send_batch_alerts
import config as _cfg

st.title("📋 Attendance Log")
st.caption("View, filter, and export attendance records by date and session.")

# ── Stats row ─────────────────────────────────────────────────────────────────
try:
    stats = get_attendance_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Students Enrolled", stats["total_students"])
    c2.metric("Total Attendance Records", stats["total_records"])
    today_count = stats["by_date"].get(date.today().isoformat(), 0)
    c3.metric("Present Today (all sessions)", today_count)
except Exception as exc:
    st.warning(f"Could not load stats: {exc}")

st.divider()

# ── Filters row ───────────────────────────────────────────────────────────────
filter_col1, filter_col2, filter_col3 = st.columns([3, 2, 1])

with filter_col1:
    selected_date = st.date_input(
        "Select Date",
        value=date.today(),
        min_value=date.today() - timedelta(days=365),
        max_value=date.today(),
    )

with filter_col2:
    session_filter = st.radio(
        "Session",
        options=["Both", "FN", "AN"],
        horizontal=True,
        key="log_session_filter",
        help="Filter records by session. 'Both' shows FN and AN together.",
    )

with filter_col3:
    st.markdown("<br>", unsafe_allow_html=True)
    refresh = st.button("🔄 Refresh")

date_str = selected_date.isoformat()

# ── Attendance Table ──────────────────────────────────────────────────────────
session_arg = None if session_filter == "Both" else session_filter
records = get_attendance_by_date(date_str, session=session_arg)

session_label = f"({session_filter} session)" if session_filter != "Both" else "(all sessions)"
st.markdown(
    f"### Records for **{date_str}** {session_label} — {len(records)} student(s) present"
)

if not records:
    st.info(
        f"No attendance recorded for {date_str} {session_label}.  "
        "Run a Batch Classroom Scan or Live Attendance session to populate records.",
        icon="ℹ️",
    )
else:
    # ── Annotate with alert_sent status ───────────────────────────────────────
    # Present students never get an alert → "N/A"
    # Absent students: check notifications_log
    for rec in records:
        # All records in attendance are "Present" — alerts are for absentees only
        rec["alert_sent"] = "N/A (Present)"

    # Build display DataFrame
    df = pd.DataFrame(records)

    # Reorder / rename columns for display
    display_cols = [
        "date", "session", "name", "roll_no", "class_section",
        "student_id", "timestamp", "status",
        "matched_angle", "match_distance", "alert_sent",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    df_display = df[display_cols].rename(columns={
        "date":           "Date",
        "session":        "Session",
        "name":           "Name",
        "roll_no":        "Roll No",
        "class_section":  "Class/Section",
        "student_id":     "Student ID",
        "timestamp":      "Time",
        "status":         "Status",
        "matched_angle":  "Matched Angle",
        "match_distance": "Distance",
        "alert_sent":     "Alert Sent",
    })

    # Colour-code by matched_angle
    def _angle_color(angle: str) -> str:
        colors = {
            "front":         "background-color: #1a3a2a; color: #80ffb0",
            "left_profile":  "background-color: #1a2a3a; color: #80c8ff",
            "right_profile": "background-color: #2a1a3a; color: #c880ff",
            "tilt_up":       "background-color: #3a2a1a; color: #ffb880",
            "tilt_down":     "background-color: #3a1a1a; color: #ff8080",
        }
        return colors.get(angle, "")

    def _style_df(row):
        angle = row.get("Matched Angle", "")
        style = _angle_color(angle)
        return [style if col == "Matched Angle" else "" for col in row.index]

    st.dataframe(
        df_display.style.apply(_style_df, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # ── Download CSV ──────────────────────────────────────────────────────────
    csv_bytes = df_display.to_csv(index=False).encode("utf-8")
    fname = f"attendance_{date_str}"
    if session_filter != "Both":
        fname += f"_{session_filter}"
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv_bytes,
        file_name=f"{fname}.csv",
        mime="text/csv",
    )

    # ── Match Quality Insights ────────────────────────────────────────────────
    with st.expander("🔍 Recognition Quality Breakdown", expanded=False):
        st.caption(
            "Lower distance = more confident match.  "
            "Values above 0.45 (threshold) are never stored (those would be 'Unknown')."
        )

        if "match_distance" in df.columns:
            fig = px.histogram(
                df,
                x="match_distance",
                nbins=20,
                title=f"Match Distance Distribution — {date_str} {session_label}",
                labels={"match_distance": "Cosine Distance"},
                color_discrete_sequence=["#00c8a0"],
            )
            fig.add_vline(x=0.45, line_dash="dash", line_color="red",
                          annotation_text="Threshold (0.45)")
            st.plotly_chart(fig, use_container_width=True)

        if "matched_angle" in df.columns:
            angle_counts = df["matched_angle"].value_counts().reset_index()
            angle_counts.columns = ["Angle", "Count"]
            fig2 = px.pie(
                angle_counts,
                names="Angle",
                values="Count",
                title="Match Angle Distribution",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Session breakdown if viewing both
        if session_filter == "Both" and "session" in df.columns:
            sess_counts = df["session"].value_counts().reset_index()
            sess_counts.columns = ["Session", "Count"]
            fig3 = px.bar(
                sess_counts,
                x="Session", y="Count",
                title="Records by Session",
                color="Session",
                color_discrete_map={"FN": "#0099cc", "AN": "#cc6600"},
            )
            st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Absentee Alerts ───────────────────────────────────────────────────────────
# Shown when a specific session (FN or AN) is selected — not for "Both",
# since alerts are always per-session.
if session_filter == "Both":
    st.info(
        "📢 **To send absentee alerts**, select **FN** or **AN** from the Session "
        "filter above, then the Send Alerts button will appear here.",
        icon="ℹ️",
    )
else:
    st.markdown(f"### 📢 Absentee Alerts — {session_filter} Session · {date_str}")

    with st.spinner("Computing absentees…"):
        absentees = get_absentees(date_str, session_filter)

    if not absentees:
        st.success(
            "All enrolled students were marked present for this session. No alerts needed.",
            icon="✅",
        )
    else:
        st.warning(
            f"**{len(absentees)} absentee(s)** not marked present in the "
            f"**{session_filter}** session on **{date_str}**.",
            icon="⚠️",
        )

        # Build status table
        rows = []
        pending_count = 0
        for s in absentees:
            log = get_notification_log(s["student_id"], date_str, session_filter)
            if log and log.get("status") == "sent":
                alert_status = "✅ Sent"
            elif log and log.get("status") == "failed":
                alert_status = "❌ Failed — will retry"
                pending_count += 1
            elif s.get("parent_telegram_chat_id"):
                alert_status = "⏳ Pending"
                pending_count += 1
            else:
                alert_status = "⚠️ No parent linked"

            rows.append({
                "Name":          s["name"],
                "Roll No":       s.get("roll_no", "—"),
                "Class/Section": s.get("class_section", "—"),
                "Parent Linked": "✅ Yes" if s.get("parent_telegram_chat_id") else "❌ No",
                "Alert Status":  alert_status,
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Send button
        bot_ok = bool(_cfg.TELEGRAM_BOT_TOKEN)
        if not bot_ok:
            st.error(
                "TELEGRAM_BOT_TOKEN is not configured. "
                "Set it in .env and restart the app.",
                icon="🔴",
            )

        btn_label = (
            f"📨 Send Absentee Alerts  ({pending_count} pending)"
            if pending_count > 0
            else "📨 All Alerts Already Sent"
        )

        if st.button(
            btn_label,
            type="primary",
            key="log_send_alerts_btn",
            use_container_width=True,
            disabled=(not bot_ok or pending_count == 0),
        ):
            with st.spinner("Sending Telegram alerts…"):
                results = send_batch_alerts(absentees, date_str, session_filter)

            for r in results:
                student_name = next(
                    (s["name"] for s in absentees if s["student_id"] == r["student_id"]),
                    r["student_id"],
                )
                if r["status"] == "sent":
                    st.success(f"✅ **{student_name}** — Alert sent!", icon="✅")
                elif r["status"] == "already_sent":
                    st.info(f"⏭️ **{student_name}** — Already sent previously", icon="ℹ️")
                elif r["status"] == "skipped_no_chat_id":
                    st.warning(f"⚠️ **{student_name}** — No parent Telegram linked yet", icon="⚠️")
                elif r["status"] == "failed":
                    st.error(f"❌ **{student_name}** — Failed: {r.get('error')}", icon="❌")

            st.rerun()

st.divider()

# ── Trend Chart ───────────────────────────────────────────────────────────────
st.markdown("### 📈 Attendance Trend (all time)")
try:
    stats = get_attendance_stats()
    if stats["by_date"]:
        trend_df = pd.DataFrame(
            list(stats["by_date"].items()),
            columns=["Date", "Students Present"],
        ).sort_values("Date")

        fig4 = px.bar(
            trend_df,
            x="Date",
            y="Students Present",
            title="Daily Attendance Count (all sessions combined)",
            color="Students Present",
            color_continuous_scale="teal",
        )
        fig4.update_layout(showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("No attendance data yet to plot.", icon="📊")
except Exception as exc:
    st.warning(f"Could not load trend data: {exc}")
