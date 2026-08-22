"""
portals/admin_portal/user_management.py
=========================================
Admin — User Management (Phase 10).

Features:
  - Table of all users (filter by role)
  - Create User form (role-aware: section picker for teacher, student-link for student)
  - Deactivate / Reactivate toggle
  - Password reset
  - Delete user
  - All mutations logged to audit_log

Theme: Dark, information-dense, technical.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("admin")
update_last_activity()

# ── Admin portal badge CSS — minimal, inherits global theme ──────────────────
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
.health-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 16px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

user = get_current_user()
actor_id = user.get("user_id", "admin")

from auth.user_operations import (
    create_user, get_all_users, get_user_by_id,
    deactivate_user, reactivate_user, reset_password, delete_user,
    log_audit,
)
from database.mongo_client import get_db
from database.db_operations import get_class_sections

db = get_db()

st.markdown('<div class="admin-badge">🛠️ ADMIN PORTAL</div>', unsafe_allow_html=True)
st.title("👥 User Management")
st.caption("Create, edit, deactivate, and manage all user accounts.")
st.divider()

# ── Role filter tabs ───────────────────────────────────────────────────────────
tab_all, tab_create = st.tabs(["📋 All Users", "➕ Create User"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB: All Users
# ═══════════════════════════════════════════════════════════════════════════════
with tab_all:
    # ── Filters ────────────────────────────────────────────────────────────────
    f_col1, f_col2 = st.columns([2, 2])
    with f_col1:
        role_filter_sel = st.radio(
            "Filter by role:",
            ["All", "admin", "teacher", "student"],
            horizontal=True,
            key="uman_role_filter",
        )
    with f_col2:
        all_sections = ["All Classes"] + get_class_sections()
        section_filter_sel = st.selectbox(
            "Filter by class:",
            options=all_sections,
            key="uman_section_filter",
        )

    rf = None if role_filter_sel == "All" else role_filter_sel
    users = get_all_users(role_filter=rf)

    # Apply class filter (only meaningful for student/teacher roles)
    if section_filter_sel != "All Classes":
        users = [
            u for u in users
            if section_filter_sel in u.get("assigned_sections", [])
        ]

    if not users:
        st.info("No users found for the selected filters.", icon="ℹ️")
    else:
        # ── Pre-compute attendance % for student users ─────────────────────────
        # Attendance student_ids are uppercase; usernames are lowercase → normalize
        total_sessions = db["attendance"].distinct("date")
        n_possible = len(total_sessions) * 2  # FN + AN per day

        def _att_pct(username: str) -> str:
            """Return 'XX.X%' attendance rate or '—' for non-students."""
            uid_upper = username.upper()
            present = db["attendance"].count_documents(
                {"student_id": uid_upper, "status": "Present"}
            )
            if n_possible == 0:
                return "—"
            return f"{present / n_possible * 100:.1f}%"

        st.markdown(f"**{len(users)} user(s)** found")

        # ── Build display dataframe ────────────────────────────────────────────
        df_rows = []
        for u in users:
            sections_val = ", ".join(u.get("assigned_sections", [])) or "—"
            att_pct = _att_pct(u["username"]) if u["role"] == "student" else "—"
            df_rows.append({
                "Username":    u["username"],
                "Full Name":   u.get("full_name", "—"),
                "Role":        u["role"],
                "Class":       sections_val,
                "Attendance %": att_pct,
                "Status":      "✅ Active" if u.get("is_active", True) else "🔴 Inactive",
                "Last Login":  str(u.get("last_login", "Never"))[:19],
                "user_id":     u["user_id"],
            })
        df = pd.DataFrame(df_rows)
        st.dataframe(df.drop(columns=["user_id"]), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Manage Individual User")

        user_labels = {f"{u['username']} ({u['role']})": u["user_id"] for u in users}
        selected_label = st.selectbox("Select User", options=list(user_labels.keys()), key="uman_select")
        sel_uid = user_labels[selected_label]
        sel_user = next((u for u in users if u["user_id"] == sel_uid), None)

        if sel_user:
            c_info, c_actions = st.columns([2, 1])

            with c_info:
                st.markdown(f"**Username:** `{sel_user['username']}`")
                st.markdown(f"**Full Name:** {sel_user.get('full_name','—')}")
                st.markdown(f"**Role:** `{sel_user['role']}`")
                st.markdown(f"**Status:** {'✅ Active' if sel_user.get('is_active', True) else '🔴 Inactive'}")
                st.markdown(f"**Class/Sections:** {', '.join(sel_user.get('assigned_sections', [])) or '—'}")
                if sel_user["role"] == "student":
                    st.markdown(f"**Attendance:** {_att_pct(sel_user['username'])}")
                st.markdown(f"**Created:** {str(sel_user.get('created_on','—'))[:19]}")

            with c_actions:
                st.markdown("**Actions**")

                # Activate / Deactivate
                is_active = sel_user.get("is_active", True)
                if is_active:
                    if st.button("🔴 Deactivate", key=f"deact_{sel_uid}", use_container_width=True):
                        deactivate_user(sel_uid, actor_id)
                        st.success(f"Deactivated {sel_user['username']}.")
                        st.rerun()
                else:
                    if st.button("✅ Reactivate", key=f"react_{sel_uid}", use_container_width=True):
                        reactivate_user(sel_uid, actor_id)
                        st.success(f"Reactivated {sel_user['username']}.")
                        st.rerun()

                st.divider()
                # Password reset
                new_pw = st.text_input(
                    "New password (min 8 chars)",
                    type="password",
                    key=f"pw_{sel_uid}",
                    placeholder="Leave blank to skip",
                )
                if st.button("🔑 Reset Password", key=f"pwreset_{sel_uid}", use_container_width=True):
                    if not new_pw:
                        st.error("Enter a new password.", icon="❌")
                    else:
                        ok, err = reset_password(sel_uid, new_pw, actor_id)
                        if ok:
                            st.success("Password reset successfully.")
                        else:
                            st.error(err)

                st.divider()
                # Delete
                if st.button("🗑️ Delete User", key=f"del_{sel_uid}",
                             type="secondary", use_container_width=True):
                    st.session_state[f"confirm_del_{sel_uid}"] = True

                if st.session_state.get(f"confirm_del_{sel_uid}"):
                    st.warning(f"Delete **{sel_user['username']}**? This cannot be undone.")
                    y_col, n_col = st.columns(2)
                    if y_col.button("Yes, delete", key=f"yes_del_{sel_uid}", type="primary"):
                        delete_user(sel_uid, actor_id)
                        st.success("User deleted.")
                        st.session_state.pop(f"confirm_del_{sel_uid}", None)
                        st.rerun()
                    if n_col.button("Cancel", key=f"no_del_{sel_uid}"):
                        st.session_state.pop(f"confirm_del_{sel_uid}", None)
                        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB: Create User
# ═══════════════════════════════════════════════════════════════════════════════
with tab_create:
    st.markdown("### New User Details")

    # Role selector OUTSIDE the form so role-specific sections react immediately
    c3_outer, c4_outer = st.columns(2)
    new_role = c3_outer.selectbox(
        "Role *",
        ["admin", "teacher", "student"],
        key="create_role_outer",
        help="Select the role first — additional fields will appear below.",
    )

    # ── Role-specific fields (reactive, outside form) ─────────────────────────
    new_linked_student = None
    new_sections       = []

    # Single source of truth: classes collection
    sections_in_db = get_class_sections()

    if new_role == "student":
        st.markdown("#### Student Account Settings")
        if sections_in_db:
            sel_section = st.selectbox(
                "Class Section *",
                options=sections_in_db,
                key="create_student_section",
                help="The class/section this student belongs to.",
            )
            new_sections = [sel_section]
        else:
            manual_sec = st.text_input(
                "Class Section (e.g. | AIDS - A)",
                key="create_student_section_manual",
                help="No classes configured yet — ask admin to set up classes first.",
            )
            new_sections = [manual_sec.strip()] if manual_sec.strip() else []

    elif new_role == "teacher":
        st.markdown("#### Teacher Account Settings")
        if sections_in_db:
            new_sections = st.multiselect(
                "Assigned Sections *",
                options=sections_in_db,
                key="create_sections",
                help="Teacher can view and override attendance for these sections.",
            )
        else:
            manual_sections = st.text_input(
                "Assigned Sections (comma-separated)",
                key="create_sections_manual",
                help="No classes configured yet — ask admin to set up classes first.",
            )
            new_sections = [s.strip() for s in manual_sections.split(",") if s.strip()]

    # admin role: no extra fields needed
    elif new_role == "admin":
        st.info("Admin accounts have full portal access. No additional settings required.", icon="🛡️")

    st.divider()

    # ── Main user details form ─────────────────────────────────────────────────
    with st.form("create_user_form", clear_on_submit=True):
        st.markdown("#### Account Details")

        c1, c2 = st.columns(2)
        new_username  = c1.text_input("Username *", placeholder="e.g. john.teacher")
        new_full_name = c2.text_input("Full Name *", placeholder="e.g. John Kumar")

        new_email = st.text_input("Email (optional)", placeholder="e.g. john@college.edu")

        new_password = st.text_input(
            "Password * (min 8 chars)",
            type="password",
            placeholder="Enter initial password",
        )

        submitted = st.form_submit_button(
            "✅ Create User", type="primary", use_container_width=True
        )

    if submitted:
        ok, result = create_user(
            username=new_username,
            password=new_password,
            role=new_role,
            full_name=new_full_name,
            email=new_email,
            linked_student_id=new_linked_student,
            assigned_sections=new_sections,
            created_by=actor_id,
        )
        if ok:
            log_audit(
                actor_user_id=actor_id,
                actor_role="admin",
                action="user_created",
                target=f"username={new_username} role={new_role}",
                old_value="",
                new_value=f"user_id={result}",
            )
            st.success(
                f"✅ User **{new_username}** ({new_role}) created successfully! "
                f"User ID: `{result}`",
                icon="✅",
            )
        else:
            st.error(f"❌ {result}", icon="❌")

st.caption(f"EngageLens v2.0 · Admin Portal · {user.get('full_name','')}")
