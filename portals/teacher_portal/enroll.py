"""
portals/teacher_portal/enroll.py
===================================
Teacher — Enroll Student (Phase 10).
Ported from pages/4_Enroll_Student.py with role guard added.
st.set_page_config removed (handled by app.py).
"""

from pathlib import Path
from datetime import date
import io

import cv2
import numpy as np
import streamlit as st
from PIL import Image

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("teacher", "admin")
update_last_activity()



from database.mongo_client import get_db, MongoConnectionError
from database.db_operations import (
    insert_student, get_all_students, get_student_by_id, delete_student,
    get_class_sections,
)
from face_recognition_module.enroll import enroll_student, validate_enrollment_image
import config as _cfg

@st.cache_resource(show_spinner="Loading InsightFace models…")
def _load_detector():
    from face_recognition_module.detector import load_detector
    try:
        return load_detector(), None
    except RuntimeError as exc:
        return None, str(exc)

detector, det_err = _load_detector()
if det_err:
    st.error(f"InsightFace could not load: {det_err}", icon="⚠️")
    st.stop()

def _decode_bytes(raw_bytes):
    arr = np.frombuffer(raw_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def _decode_upload(uploaded):
    if uploaded is None:
        return None
    return _decode_bytes(uploaded.getvalue())

def _validation_badge(img):
    valid, msg = validate_enrollment_image(img)
    if valid:
        if "⚠" in msg:
            st.warning(msg, icon="⚠️")
        else:
            st.success(msg, icon="✅")
    else:
        st.error(msg, icon="❌")
    return valid

def _make_qr_image(url):
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
    except ImportError:
        return None

def _show_telegram_link_ui(student_id):
    bot_username = _cfg.TELEGRAM_BOT_USERNAME
    deep_link    = f"https://t.me/{bot_username}?start={student_id}"
    st.markdown("---\n### 📱 Parent Telegram Linking")
    link_col, qr_col = st.columns([3, 2])
    with link_col:
        st.markdown(f"**Deep link for {student_id}:**")
        st.code(deep_link, language=None)
        st.markdown(f"[🔗 Open in Telegram]({deep_link})")
        student_doc = get_student_by_id(student_id)
        if student_doc and student_doc.get("parent_telegram_chat_id"):
            st.success(f"✅ Parent linked (chat_id: `{student_doc['parent_telegram_chat_id']}`)")
        else:
            st.warning("⏳ Waiting for parent to link…")
    with qr_col:
        qr_img = _make_qr_image(deep_link)
        if qr_img:
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Scan with Telegram", width=200)

def _submit_enrollment(student_id, name, angle_image_pairs, roll_no="", class_section=""):
    if not all([student_id.strip(), name.strip(), roll_no.strip(), class_section.strip()]):
        st.error("All fields are required.", icon="❌")
        return
    if not angle_image_pairs:
        st.error("No photos provided. Upload at least 2 angle photos.", icon="❌")
        return
    if get_student_by_id(student_id.strip()):
        st.error(f"Student ID **{student_id}** already enrolled. Delete existing record first.", icon="❌")
        return
    with st.spinner("Processing photos…"):
        success, angle_embeddings, errors = enroll_student(
            student_id=student_id.strip(), name=name.strip(), angle_image_pairs=angle_image_pairs,
        )
    if not success:
        st.error("**Enrollment failed.**", icon="❌")
        for err in errors:
            st.error(err)
        return
    ok = insert_student(
        student_id=student_id.strip(), name=name.strip(),
        angle_embeddings=angle_embeddings, roll_no=roll_no.strip(), class_section=class_section.strip(),
    )
    if ok:
        angles_stored = [ae["angle"] for ae in angle_embeddings]
        st.success(
            f"✅ **{name.strip()}** (ID: {student_id.strip()}) enrolled! "
            f"Roll: {roll_no.strip()} · Section: {class_section.strip()} · "
            f"Angles: {', '.join(angles_stored)}",
            icon="🎓",
        )
        st.balloons()
        _show_telegram_link_ui(student_id.strip())
        for k in ["cam_front", "cam_left", "cam_right"]:
            st.session_state.pop(k, None)
    else:
        st.error(f"Student ID {student_id} already exists.", icon="❌")

# ── Page ───────────────────────────────────────────────────────────────────────
st.title("🧑‍🎓 Enroll Student")
st.caption("Add a new student with multi-angle photos (front + at least one profile).")

# Load class sections once (from classes collection — admin-managed)
_class_sections = get_class_sections()
_section_placeholder = "Select a class section"

tab_upload, tab_camera, tab_manage = st.tabs(["📁 Upload Photos", "📷 Live Camera", "📋 Manage Students"])

# TAB 1: Upload
with tab_upload:
    with st.form("enrollment_form", clear_on_submit=False):
        st.markdown("### Student Information")
        c1, c2 = st.columns(2)
        student_id_up = c1.text_input("Student ID *", placeholder="e.g. 24ADR122", key="up_sid")
        name_up       = c2.text_input("Full Name *",  placeholder="e.g. Jane Doe", key="up_name")
        c3, c4 = st.columns(2)
        roll_no_up = c3.text_input("Roll No *", placeholder="e.g. 24ADR122", key="up_roll")
        if _class_sections:
            class_section_up = c4.selectbox(
                "Class / Section *",
                options=_class_sections,
                key="up_section",
            )
        else:
            class_section_up = c4.text_input(
                "Class / Section *",
                placeholder="No classes yet — ask admin",
                key="up_section",
            )
        st.divider()
        col_front, col_left, col_right = st.columns(3)
        with col_front:
            st.markdown("#### 📷 Front *(required)*")
            front_file = st.file_uploader("Front photo", type=["jpg","jpeg","png"], key="front_upload")
        with col_left:
            st.markdown("#### ◀️ Left Profile *(recommended)*")
            left_file = st.file_uploader("Left profile", type=["jpg","jpeg","png"], key="left_upload")
        with col_right:
            st.markdown("#### ▶️ Right Profile *(recommended)*")
            right_file = st.file_uploader("Right profile", type=["jpg","jpeg","png"], key="right_upload")
        submitted_up = st.form_submit_button("🎓 Enroll Student", use_container_width=True, type="primary")

    if any([front_file, left_file, right_file]):
        st.markdown("### Previews & Validation")
        for col, uploaded, label in [
            (st.columns(3)[0], front_file, "Front"),
            (st.columns(3)[1], left_file, "Left"),
            (st.columns(3)[2], right_file, "Right"),
        ]:
            img = _decode_upload(uploaded)
            if img is not None:
                with col:
                    st.image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), caption=label, use_container_width=True)
                    _validation_badge(img)

    if submitted_up:
        pairs = [(ang, _decode_upload(f)) for ang, f in
                 [("front", front_file), ("left_profile", left_file), ("right_profile", right_file)]
                 if f is not None]
        pairs = [(a, img) for a, img in pairs if img is not None]
        if not pairs:
            st.error("Please upload at least the Front photo.", icon="❌")
        else:
            _submit_enrollment(student_id_up, name_up, pairs, roll_no_up, class_section_up)

# TAB 2: Camera
with tab_camera:
    st.markdown("### 📷 Live Camera Enrollment")
    cc1, cc2 = st.columns(2)
    student_id_cam = cc1.text_input("Student ID *", placeholder="e.g. 24ADR122", key="cam_sid")
    name_cam       = cc2.text_input("Full Name *",  placeholder="e.g. Jane Doe",  key="cam_name")
    cc3, cc4 = st.columns(2)
    roll_no_cam = cc3.text_input("Roll No *", placeholder="e.g. 24ADR122", key="cam_roll")
    if _class_sections:
        class_section_cam = cc4.selectbox(
            "Class / Section *",
            options=_class_sections,
            key="cam_section",
        )
    else:
        class_section_cam = cc4.text_input(
            "Class / Section *",
            placeholder="No classes yet — ask admin",
            key="cam_section",
        )
    st.divider()
    ANGLES = [
        ("cam_front", "front",        "📷 Front-Facing", "Look directly at the camera."),
        ("cam_left",  "left_profile", "◀️ Left Profile", "Turn ~45° to your left."),
        ("cam_right", "right_profile","▶️ Right Profile", "Turn ~45° to your right."),
    ]
    angle_cols = st.columns(3)
    for col, (state_key, angle_id, label, instruction) in zip(angle_cols, ANGLES):
        with col:
            st.markdown(f"#### {label}")
            st.caption(instruction)
            cam_img = st.camera_input(f"Capture {label}", key=f"widget_{state_key}", help=instruction)
            if cam_img is not None:
                st.session_state[state_key] = cam_img.getvalue()
            stored = st.session_state.get(state_key)
            if stored:
                img_bgr = _decode_bytes(stored)
                if img_bgr is not None:
                    st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), caption=f"✅ {label}", use_container_width=True)
                    _validation_badge(img_bgr)
                    if st.button(f"🔄 Retake", key=f"retake_{state_key}"):
                        st.session_state.pop(state_key, None)
                        st.rerun()
            else:
                st.caption("_Not captured yet_")
    st.divider()
    captured = {aid: st.session_state.get(sk) for sk, aid, *_ in ANGLES if st.session_state.get(sk)}
    front_captured = st.session_state.get("cam_front") is not None
    n_captured = len(captured)
    if n_captured >= 2 and front_captured:
        st.success(f"**{n_captured}/3** angles ready.", icon="✅")
    else:
        st.warning("Capture Front + at least one profile to enable enrollment.", icon="⚠️")
    if st.button(
        "🎓 Enroll with Captured Photos", key="cam_enroll_btn", type="primary",
        use_container_width=True,
        disabled=(n_captured < 2 or not front_captured or not all(
            [student_id_cam.strip(), name_cam.strip(), roll_no_cam.strip(), class_section_cam.strip()]
        )),
    ):
        cam_pairs = [(aid, _decode_bytes(st.session_state[sk]))
                     for sk, aid, *_ in ANGLES if st.session_state.get(sk)]
        cam_pairs = [(a, img) for a, img in cam_pairs if img is not None]
        _submit_enrollment(student_id_cam, name_cam, cam_pairs, roll_no_cam, class_section_cam)

# TAB 3: Manage
with tab_manage:
    st.markdown("### Enrolled Students")

    from database.db_operations import update_student_info

    students = get_all_students()
    if not students:
        st.info("No students enrolled yet.", icon="ℹ️")
    else:
        st.markdown(f"**{len(students)} student(s) enrolled**")
        search = st.text_input("🔍 Filter", placeholder="Search by name, ID or roll no…", key="manage_search")
        filtered = [s for s in students
                    if not search or any(search.lower() in str(s.get(f, "")).lower()
                    for f in ["name", "student_id", "roll_no", "class_section"])]

        for student in filtered:
            sid      = student["student_id"]
            edit_key = f"edit_{sid}"
            conf_key = f"conf_{sid}"

            with st.container(border=True):
                # ── Top row: info + action buttons ────────────────────────────
                c_info, c_angles, c_tg, c_action = st.columns([3, 3, 2, 2])

                with c_info:
                    st.markdown(f"**{student['name']}**")
                    st.caption(f"ID: `{sid}`")
                    st.caption(
                        f"Roll: `{student.get('roll_no', '—')}` · "
                        f"Section: `{student.get('class_section', '—') or '—'}`"
                    )

                with c_angles:
                    angles = [enc["angle"] for enc in student.get("face_encodings", [])]
                    st.markdown("**Angles:**")
                    for a in angles:
                        st.markdown(f"- {a.replace('_', ' ').title()}")
                    if len(angles) < 2:
                        st.warning("Only 1 angle — recognition may be poor.", icon="⚠️")

                with c_tg:
                    chat_id = student.get("parent_telegram_chat_id")
                    if chat_id:
                        st.success("✅ Linked", icon="📲")
                    else:
                        st.warning("⏳ Not linked", icon="📲")

                with c_action:
                    # Edit toggle
                    if not st.session_state.get(edit_key):
                        if st.button("✏️ Edit", key=f"btn_edit_{sid}", use_container_width=True):
                            st.session_state[edit_key] = True
                            st.rerun()
                    else:
                        if st.button("✖ Cancel", key=f"btn_cancel_{sid}", use_container_width=True):
                            st.session_state.pop(edit_key, None)
                            st.rerun()

                    st.write("")  # spacer

                    # Delete button
                    if st.button("🗑 Delete", key=f"del_{sid}", type="secondary",
                                 use_container_width=True):
                        st.session_state[conf_key] = True

                    if st.session_state.get(conf_key):
                        st.warning("Delete this student and all their attendance records?")
                        y, n = st.columns(2)
                        if y.button("Yes", key=f"yes_{sid}", type="primary"):
                            delete_student(sid)
                            st.success(f"Deleted {student['name']}.")
                            st.session_state.pop(conf_key, None)
                            st.session_state.pop(edit_key, None)
                            st.rerun()
                        if n.button("No", key=f"no_{sid}"):
                            st.session_state.pop(conf_key, None)
                            st.rerun()

                # ── Inline edit form (shown below the card when editing) ───────
                if st.session_state.get(edit_key):
                    st.divider()
                    st.markdown("#### ✏️ Edit Student Info")

                    with st.form(key=f"edit_form_{sid}", clear_on_submit=False):
                        e1, e2, e3 = st.columns(3)
                        new_name    = e1.text_input(
                            "Full Name *",
                            value=student.get("name", ""),
                            key=f"ef_name_{sid}",
                        )
                        new_roll    = e2.text_input(
                            "Roll No",
                            value=student.get("roll_no", ""),
                            key=f"ef_roll_{sid}",
                        )
                        # Section: dropdown if classes exist, else text
                        cur_section = student.get("class_section", "")
                        if _class_sections:
                            _default_idx = _class_sections.index(cur_section) if cur_section in _class_sections else 0
                            new_section = e3.selectbox(
                                "Class / Section",
                                options=_class_sections,
                                index=_default_idx,
                                key=f"ef_sec_{sid}",
                            )
                        else:
                            new_section = e3.text_input(
                                "Class / Section",
                                value=cur_section,
                                placeholder="e.g. | AIDS - B",
                                key=f"ef_sec_{sid}",
                            )

                        save_btn = st.form_submit_button(
                            "💾 Save Changes",
                            type="primary",
                            use_container_width=True,
                        )

                    if save_btn:
                        ok, err = update_student_info(
                            student_id=sid,
                            name=new_name,
                            roll_no=new_roll,
                            class_section=new_section,
                        )
                        if ok:
                            st.success(
                                f"✅ **{new_name}** updated successfully!",
                                icon="✅",
                            )
                            st.session_state.pop(edit_key, None)
                            st.rerun()
                        else:
                            st.error(f"❌ {err}", icon="❌")
