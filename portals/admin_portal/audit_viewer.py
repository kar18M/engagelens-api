"""
portals/admin_portal/audit_viewer.py
======================================
Admin — Audit Log Viewer (Phase 10).

Searchable + filterable view of every admin/teacher action logged in audit_log.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("admin")
update_last_activity()

st.markdown("""
<style>
.admin-badge {
    background: var(--bg2);
    border: 1px solid var(--border);
    color: var(--dark);
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 10px;
}
.status-ok  { color: #2D6A4F; font-weight: 600; }
.status-err { color: #991B1B; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

user = get_current_user()
from auth.user_operations import get_audit_log, get_all_users
from database.mongo_client import get_db

db = get_db()

st.markdown('<div class="admin-badge">🛠️ ADMIN PORTAL</div>', unsafe_allow_html=True)
st.title("🔍 Audit Log")
st.caption("Immutable record of every admin and teacher action in the system.")
st.divider()

# ── Filters ────────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 2])

with col_f1:
    # Actor filter — list all users
    all_users = get_all_users()
    actor_opts = {"All": None}
    actor_opts.update({f"{u['username']} ({u['role']})": u["user_id"] for u in all_users})
    selected_actor_label = st.selectbox("Actor (User)", list(actor_opts.keys()), key="audit_actor")
    selected_actor = actor_opts[selected_actor_label]

with col_f2:
    ACTION_TYPES = [
        "All",
        "attendance_override",
        "user_created",
        "user_deactivated",
        "user_reactivated",
        "user_deleted",
        "password_reset",
        "role_changed",
        "config_changed",
    ]
    selected_action = st.selectbox("Action Type", ACTION_TYPES, key="audit_action")
    action_filter = None if selected_action == "All" else selected_action

with col_f3:
    date_from = st.date_input(
        "From", value=datetime.utcnow().date() - timedelta(days=30), key="audit_from"
    )

with col_f4:
    date_to = st.date_input(
        "To", value=datetime.utcnow().date(), key="audit_to"
    )

limit = st.slider("Max rows", 20, 500, 100, 10, key="audit_limit")

# ── Load records ───────────────────────────────────────────────────────────────
from datetime import date as date_type
records = get_audit_log(
    actor_user_id=selected_actor,
    action=action_filter,
    date_from=datetime.combine(date_from, datetime.min.time()),
    date_to=datetime.combine(date_to, datetime.max.time()),
    limit=limit,
)

st.markdown(f"**{len(records)} record(s)** found (newest first)")

if not records:
    st.info("No audit log entries match the selected filters.", icon="📋")
else:
    df = pd.DataFrame(records)
    display_cols = ["timestamp", "actor_user_id", "actor_role", "action", "target", "old_value", "new_value"]
    display_cols = [c for c in display_cols if c in df.columns]
    df_disp = df[display_cols].rename(columns={
        "timestamp":     "Time (UTC)",
        "actor_user_id": "Actor",
        "actor_role":    "Role",
        "action":        "Action",
        "target":        "Target",
        "old_value":     "Before",
        "new_value":     "After",
    })

    # Color-code action column by type
    def _highlight_action(val):
        colors = {
            "attendance_override": "color:#1D4ED8;font-weight:600",
            "user_created":        "color:#2D6A4F;font-weight:600",
            "user_deactivated":    "color:#92400E;font-weight:600",
            "user_deleted":        "color:#991B1B;font-weight:600",
            "password_reset":      "color:#6B6B6B;font-weight:600",
            "config_changed":      "color:#1A1A1A;font-weight:600",
        }
        return colors.get(val, "")

    st.dataframe(
        df_disp.style.applymap(_highlight_action, subset=["Action"]),
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    # ── Export ─────────────────────────────────────────────────────────────────
    csv = df_disp.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export Audit Log CSV",
        data=csv,
        file_name=f"audit_log_{date_from}_{date_to}.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.divider()

# ── Action type summary chart ──────────────────────────────────────────────────
st.markdown("### Action Distribution (all time)")
try:
    pipeline = [{"$group": {"_id": "$action", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    agg = list(db["audit_log"].aggregate(pipeline))
    if agg:
        agg_df = pd.DataFrame(agg).rename(columns={"_id": "Action", "count": "Count"})
        import plotly.express as px
        fig = px.bar(
            agg_df, x="Count", y="Action", orientation="h",
            color="Count", color_continuous_scale=[[0,"#E8E8E6"],[1,"#1A1A1A"]],
            title="Total Audit Events by Type",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#6B6B6B", family="Outfit"),
            height=300,
            showlegend=False,
        )
        fig.update_xaxes(gridcolor="#E8E8E6")
        fig.update_yaxes(gridcolor="#E8E8E6")
        st.plotly_chart(fig, use_container_width=True)
except Exception as exc:
    st.warning(f"Could not load audit distribution: {exc}")

st.caption(f"EngageLens v2.0 · Admin Portal · {user.get('full_name','')}")
