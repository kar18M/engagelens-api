"""
portals/teacher_portal/alerts.py
===================================
Teacher — Absentee Alerts Management (Phase 10).

Pick a date + session → see absentees with their Telegram link status
→ send alerts with one click.
"""

import streamlit as st
import pandas as pd
from datetime import date

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("teacher", "admin")
update_last_activity()



user = get_current_user()
assigned_sections = user.get("assigned_sections", [])
role = user.get("role")

import config
from database.mongo_client import get_db
from database.db_operations import get_absentees, get_notification_log
from notifications.telegram_bot import send_batch_alerts

db = get_db()

st.title("📢 Absentee Alerts")
st.caption("Compute absentees for a session and send Telegram notifications to linked parents.")
st.divider()

col_d, col_s = st.columns(2)
with col_d:
    alert_date = st.date_input("Date", value=date.today(), max_value=date.today(), key="alert_date")
with col_s:
    alert_session = st.radio("Session", ["FN", "AN"], horizontal=True, key="alert_session")

date_str = alert_date.isoformat()

if st.button("🔍 Compute Absentees", type="primary", use_container_width=True):
    with st.spinner("Computing absentees…"):
        all_absentees = get_absentees(date_str, alert_session)

    # Scope to teacher's sections
    if role == "teacher" and assigned_sections:
        absentees = [a for a in all_absentees if a.get("class_section") in assigned_sections]
    else:
        absentees = all_absentees

    st.session_state["alert_absentees"] = absentees
    st.session_state["alert_date_str"]  = date_str
    st.session_state["alert_session_cache"] = alert_session

# ── Display absentee table ─────────────────────────────────────────────────────
absentees = st.session_state.get("alert_absentees", [])
cached_date = st.session_state.get("alert_date_str")
cached_sess = st.session_state.get("alert_session_cache")

if absentees is not None and cached_date == date_str and cached_sess == alert_session:
    if not absentees:
        st.success("🎉 All students are present for this session. No alerts needed.", icon="✅")
    else:
        st.warning(f"**{len(absentees)} absentee(s)** for {alert_session} on {date_str}", icon="⚠️")

        rows = []
        all_sent = True
        for s in absentees:
            log = get_notification_log(s["student_id"], date_str, alert_session)
            if log and log.get("status") == "sent":
                status_str = "✅ Sent"
            elif log and log.get("status") == "failed":
                status_str = "❌ Failed"
                all_sent = False
            elif log and log.get("status") == "skipped_no_chat_id":
                status_str = "⚠️ No parent linked"
            else:
                status_str = "⏳ Pending"
                all_sent = False

            rows.append({
                "Name":          s["name"],
                "Roll No":       s.get("roll_no","—"),
                "Section":       s.get("class_section","—"),
                "Parent Linked": "✅" if s.get("parent_telegram_chat_id") else "❌",
                "Alert Status":  status_str,
            })

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        bot_ok = bool(config.TELEGRAM_BOT_TOKEN)
        if not bot_ok:
            st.error("TELEGRAM_BOT_TOKEN not set in .env. Alerts disabled.", icon="🔴")

        if all_sent:
            st.info("All applicable alerts have already been sent.", icon="ℹ️")
        else:
            if st.button(
                f"📨 Send Alerts to {len(absentees)} Absentee(s)",
                type="primary",
                disabled=not bot_ok,
                use_container_width=True,
                key="send_alerts_btn",
            ):
                with st.spinner("Sending Telegram alerts…"):
                    results = send_batch_alerts(absentees, date_str, alert_session)

                for r in results:
                    sname = next((s["name"] for s in absentees if s["student_id"] == r["student_id"]), r["student_id"])
                    if r["status"] == "sent":
                        st.success(f"✅ {sname} — Sent")
                    elif r["status"] == "already_sent":
                        st.info(f"⏭️ {sname} — Already sent")
                    elif r["status"] == "skipped_no_chat_id":
                        st.warning(f"⚠️ {sname} — No parent linked")
                    elif r["status"] == "failed":
                        st.error(f"❌ {sname} — Failed: {r.get('error','')}")

                st.session_state.pop("alert_absentees", None)
                st.rerun()

st.caption(f"EngageLens v2.0 · Teacher Portal · {user.get('full_name','')}")
