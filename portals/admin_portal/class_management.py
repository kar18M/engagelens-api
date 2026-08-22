"""
portals/admin_portal/class_management.py
==========================================
Admin — Class Management (admin-only).

Features:
  - View all classes with student count per class
  - Create a new class
  - Delete an empty class (blocked if students are still assigned)
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("admin")          # ← admin ONLY
update_last_activity()

from auth.user_operations import log_audit
from database.db_operations import get_all_classes, create_class, delete_class
from database.mongo_client import get_db

db = get_db()
user     = get_current_user()
actor_id = user.get("user_id", "admin")

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.cls-badge {
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
.cls-stat {
    font-size: 0.80rem;
    color: var(--muted);
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="cls-badge">🛠️ ADMIN PORTAL</div>', unsafe_allow_html=True)
st.title("🏫 Class Management")
st.caption("Create, view, and delete class sections. Only admins can manage classes.")
st.divider()

tab_all, tab_create = st.tabs(["📋 All Classes", "➕ Create Class"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB: All Classes
# ══════════════════════════════════════════════════════════════════════════════
with tab_all:
    classes = get_all_classes()

    if not classes:
        st.info("No classes found. Create one using the ➕ tab.", icon="ℹ️")
    else:
        # Build display dataframe with student counts
        rows = []
        for cls in classes:
            cnt = db["students"].count_documents({"class_section": cls["name"]})
            rows.append({
                "Class Name":   cls["name"],
                "Students":     cnt,
                "Created By":   cls.get("created_by", "—"),
                "Created On":   str(cls.get("created_on", "—"))[:19],
                "class_id":     cls["class_id"],
            })

        df = pd.DataFrame(rows)
        st.markdown(f"**{len(classes)} class(es)** configured")
        st.dataframe(
            df.drop(columns=["class_id"]),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown("### Manage Class")

        class_labels = {r["Class Name"]: r["class_id"] for r in rows}
        sel_label    = st.selectbox("Select Class", options=list(class_labels.keys()), key="cls_sel")
        sel_cls_id   = class_labels[sel_label]
        sel_cls_row  = next((r for r in rows if r["class_id"] == sel_cls_id), None)

        if sel_cls_row:
            c_info, c_action = st.columns([3, 1])
            with c_info:
                st.markdown(f"**Class Name:** `{sel_cls_row['Class Name']}`")
                st.markdown(f"**Students enrolled:** {sel_cls_row['Students']}")
                st.markdown(f"**Created by:** {sel_cls_row['Created By']}")
            with c_action:
                if st.button("🗑️ Delete Class", key=f"del_cls_{sel_cls_id}",
                             type="secondary", use_container_width=True):
                    st.session_state["confirm_del_cls"] = sel_cls_id

            if st.session_state.get("confirm_del_cls") == sel_cls_id:
                st.warning(
                    f"Delete **{sel_label}**? This cannot be undone. "
                    f"Students in this class must be reassigned first."
                )
                y_col, n_col = st.columns(2)
                if y_col.button("Yes, delete", key="yes_del_cls", type="primary"):
                    ok, err = delete_class(sel_cls_id, actor=actor_id)
                    if ok:
                        log_audit(
                            actor_user_id=actor_id,
                            actor_role="admin",
                            action="class_deleted",
                            target=f"class_id={sel_cls_id} name={sel_label}",
                            old_value=sel_label,
                            new_value="DELETED",
                        )
                        st.success(f"✅ Class **{sel_label}** deleted.")
                        st.session_state.pop("confirm_del_cls", None)
                        st.rerun()
                    else:
                        st.error(f"❌ {err}", icon="❌")
                        st.session_state.pop("confirm_del_cls", None)
                if n_col.button("Cancel", key="no_del_cls"):
                    st.session_state.pop("confirm_del_cls", None)
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB: Create Class
# ══════════════════════════════════════════════════════════════════════════════
with tab_create:
    st.markdown("### New Class")
    st.caption("Class names must be unique. Use a clear, consistent naming convention.")

    with st.form("create_class_form", clear_on_submit=True):
        new_class_name = st.text_input(
            "Class Name *",
            placeholder="e.g. | AIDS - D",
            help="Use the same format as existing classes for consistency.",
        )
        submitted = st.form_submit_button("🏫 Create Class", type="primary", use_container_width=True)

    if submitted:
        ok, result = create_class(new_class_name, created_by=actor_id)
        if ok:
            log_audit(
                actor_user_id=actor_id,
                actor_role="admin",
                action="class_created",
                target=f"name={new_class_name}",
                old_value="",
                new_value=f"class_id={result}",
            )
            st.success(f"✅ Class **{new_class_name}** created! ID: `{result}`")
        else:
            st.error(f"❌ {result}", icon="❌")

st.caption(f"EngageLens v2.0 · Admin Portal · {user.get('full_name', '')}")
