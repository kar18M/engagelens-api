"""
pages/4_Enroll_Student.py
===========================
Multi-angle student enrollment page.

Supports TWO enrollment methods:
  1. 📁 Upload Photos  — classic file-upload workflow
  2. 📷 Live Camera    — snap each angle directly from webcam using
                         Streamlit's built-in st.camera_input()

Phase 9 additions:
  - roll_no and class_section are now required enrollment fields.
  - After successful enrollment, a Telegram deep-link and QR code are shown
    so the parent can scan/click to link their chat_id.
  - Live "Parent linked ✓ / Waiting for parent to link..." status badge.
  - Manage Students tab shows roll_no, class_section, and parent link status.

Design philosophy:
  Each student is enrolled with 2–3 photos (front + profile angles).
  This is MANDATORY for robust classroom recognition accuracy — a single
  front-facing embedding will fail when students turn their heads.
  See face_recognition_module/enroll.py for the full rationale.
"""

from pathlib import Path
from datetime import date
import io

import cv2
import numpy as np
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Enroll Student — EngageLens",
    page_icon="🧑‍🎓",
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
    insert_student,
    get_all_students,
    get_student_by_id,
    delete_student,
)
from face_recognition_module.enroll import enroll_student, validate_enrollment_image
import config as _cfg

# ── Cached detector ────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _decode_bytes(raw_bytes: bytes) -> np.ndarray | None:
    """Convert raw image bytes (from file_uploader or camera_input) to BGR numpy array."""
    arr = np.frombuffer(raw_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _decode_upload(uploaded) -> np.ndarray | None:
    """Decode a Streamlit UploadedFile object."""
    if uploaded is None:
        return None
    return _decode_bytes(uploaded.getvalue())


def _validation_badge(img: np.ndarray):
    """Show a green/yellow/red validation status for a decoded image."""
    valid, msg = validate_enrollment_image(img)
    if valid:
        if "⚠" in msg:
            st.warning(msg, icon="⚠️")
        else:
            st.success(msg, icon="✅")
    else:
        st.error(msg, icon="❌")
    return valid


def _make_qr_image(url: str) -> Image.Image | None:
    """Generate a QR code PIL image for the given URL. Returns None if qrcode unavailable."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
    except ImportError:
        return None


def _show_telegram_link_ui(student_id: str):
    """
    Show the Telegram deep-link, QR code, and live parent-linked status
    for the given student_id. Called after successful enrollment.
    """
    bot_username = _cfg.TELEGRAM_BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start={student_id}"

    st.markdown("---")
    st.markdown("### 📱 Parent Telegram Linking")
    st.info(
        "Share the link or QR code below with the parent. "
        "When they open it and tap **Start**, their Telegram will be linked — "
        "you'll see '✅ Parent linked' appear below automatically on refresh.",
        icon="📲",
    )

    link_col, qr_col = st.columns([3, 2])

    with link_col:
        st.markdown(f"**Deep link for {student_id}:**")
        st.code(deep_link, language=None)
        st.markdown(f"[🔗 Open in Telegram]({deep_link})")

        # Live status — re-read from DB
        student_doc = get_student_by_id(student_id)
        if student_doc and student_doc.get("parent_telegram_chat_id"):
            st.success(
                f"✅ **Parent linked** (chat_id: `{student_doc['parent_telegram_chat_id']}`)",
                icon="✅",
            )
        else:
            st.warning(
                "⏳ Waiting for parent to link…  "
                "Refresh this page after the parent has scanned the QR code.",
                icon="📲",
            )

    with qr_col:
        qr_img = _make_qr_image(deep_link)
        if qr_img is not None:
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Scan with Telegram", width=200)
        else:
            st.caption(
                "QR code unavailable — install `qrcode[pil]`:  \n"
                "`pip install qrcode[pil]`"
            )


def _submit_enrollment(
    student_id: str,
    name: str,
    angle_image_pairs: list,
    roll_no: str = "",
    class_section: str = "",
):
    """
    Shared enrollment submission logic used by both upload and camera tabs.
    Runs enroll_student() → insert_student() → shows result + Telegram link.
    """
    if not student_id.strip():
        st.error("Student ID is required.", icon="❌")
        return
    if not name.strip():
        st.error("Full name is required.", icon="❌")
        return
    if not roll_no.strip():
        st.error("Roll No is required.", icon="❌")
        return
    if not class_section.strip():
        st.error("Class/Section is required.", icon="❌")
        return
    if not angle_image_pairs:
        st.error("No photos provided. Please capture or upload at least 2 angle photos.", icon="❌")
        return

    # Block if student already enrolled
    existing = get_student_by_id(student_id.strip())
    if existing:
        st.error(
            f"Student ID **{student_id}** is already enrolled as **{existing['name']}**.  "
            "Delete the existing record from Manage Students first.",
            icon="❌",
        )
        return

    with st.spinner("Processing photos — running face detection…"):
        success, angle_embeddings, errors = enroll_student(
            student_id=student_id.strip(),
            name=name.strip(),
            angle_image_pairs=angle_image_pairs,
        )

    if not success:
        st.error("**Enrollment failed.** Fix the issues below and try again.", icon="❌")
        for err in errors:
            st.error(err)
        return

    ok = insert_student(
        student_id=student_id.strip(),
        name=name.strip(),
        angle_embeddings=angle_embeddings,
        roll_no=roll_no.strip(),
        class_section=class_section.strip(),
    )
    if ok:
        angles_stored = [ae["angle"] for ae in angle_embeddings]
        st.success(
            f"✅ **{name.strip()}** (ID: {student_id.strip()}) enrolled!  "
            f"Roll No: {roll_no.strip()} · Section: {class_section.strip()}  \n"
            f"Angles stored: {', '.join(angles_stored)}",
            icon="🎓",
        )
        st.balloons()
        # Show Telegram linking UI immediately after enrollment
        _show_telegram_link_ui(student_id.strip())
        # Clear camera captures from session state
        for k in ["cam_front", "cam_left", "cam_right"]:
            st.session_state.pop(k, None)
    else:
        st.error(
            f"Student ID {student_id} already exists in MongoDB. Enrollment aborted.",
            icon="❌",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Page Title
# ─────────────────────────────────────────────────────────────────────────────
st.title("🧑‍🎓 Enroll Student")
st.caption(
    "Add a new student with multi-angle photos (front + at least one profile).  "
    "Choose **Upload Photos** or **Live Camera** below."
)

tab_upload, tab_camera, tab_manage = st.tabs([
    "📁 Upload Photos",
    "📷 Live Camera",
    "📋 Manage Students",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload Photos
# ═══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    with st.form("enrollment_form", clear_on_submit=False):
        st.markdown("### Student Information")
        c1, c2 = st.columns(2)
        student_id_up = c1.text_input(
            "Student ID *",
            placeholder="e.g. CS101",
            key="up_sid",
            help="Must be unique across all enrolled students.",
        )
        name_up = c2.text_input(
            "Full Name *",
            placeholder="e.g. Jane Doe",
            key="up_name",
        )

        c3, c4 = st.columns(2)
        roll_no_up = c3.text_input(
            "Roll No *",
            placeholder="e.g. 21CS045",
            key="up_roll",
            help="Used in parent alert messages. May match Student ID.",
        )
        class_section_up = c4.text_input(
            "Class / Section *",
            placeholder="e.g. CSE-A",
            key="up_section",
            help="Used in parent alert messages, e.g. 'CSE-A Class In-Charge'.",
        )

        st.divider()
        st.markdown(
            "### Enrollment Photos\n"
            "> **Why multiple angles?**  When a student turns to talk to a neighbour "
            "or look at the board, a front-only embedding may fail to match.  "
            "Storing left and right profile embeddings lets the recognizer match "
            "the student regardless of head pose in the classroom shot."
        )

        col_front, col_left, col_right = st.columns(3)

        with col_front:
            st.markdown("#### 📷 Front-Facing *(required)*")
            front_file = st.file_uploader(
                "Front photo",
                type=["jpg", "jpeg", "png"],
                key="front_upload",
                help="Student looking directly at the camera.",
            )

        with col_left:
            st.markdown("#### ◀️ Left Profile *(recommended)*")
            left_file = st.file_uploader(
                "Left profile photo",
                type=["jpg", "jpeg", "png"],
                key="left_upload",
                help="Student's face turned ~45–90° to their left.",
            )

        with col_right:
            st.markdown("#### ▶️ Right Profile *(recommended)*")
            right_file = st.file_uploader(
                "Right profile photo",
                type=["jpg", "jpeg", "png"],
                key="right_upload",
                help="Student's face turned ~45–90° to their right.",
            )

        submitted_up = st.form_submit_button(
            "🎓 Enroll Student", use_container_width=True, type="primary"
        )

    # Live previews (outside form so they render on every upload)
    any_uploaded = any([front_file, left_file, right_file])
    if any_uploaded:
        st.markdown("### Photo Previews & Validation")
        prev_c1, prev_c2, prev_c3 = st.columns(3)

        for col, uploaded, label in [
            (prev_c1, front_file,  "Front-Facing"),
            (prev_c2, left_file,   "Left Profile"),
            (prev_c3, right_file,  "Right Profile"),
        ]:
            img = _decode_upload(uploaded)
            if img is not None:
                with col:
                    st.image(
                        cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
                        caption=label,
                        use_container_width=True,
                    )
                    _validation_badge(img)

    # Process submission
    if submitted_up:
        angle_image_pairs = []
        for angle, uploaded in [
            ("front",         front_file),
            ("left_profile",  left_file),
            ("right_profile", right_file),
        ]:
            img = _decode_upload(uploaded)
            if img is not None:
                angle_image_pairs.append((angle, img))

        if not angle_image_pairs:
            st.error("Please upload at least the Front photo before submitting.", icon="❌")
        else:
            _submit_enrollment(
                student_id_up, name_up, angle_image_pairs,
                roll_no=roll_no_up, class_section=class_section_up,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Live Camera Capture
# ═══════════════════════════════════════════════════════════════════════════════
with tab_camera:
    st.markdown("### 📷 Live Camera Enrollment")
    st.info(
        "Use your webcam to capture each angle one by one.  "
        "Position the student's face in the frame, then click **📸 Take Photo**.  "
        "Review the validation result, then move to the next angle.",
        icon="💡",
    )

    # ── Student info ──────────────────────────────────────────────────────────
    cc1, cc2 = st.columns(2)
    student_id_cam = cc1.text_input(
        "Student ID *",
        placeholder="e.g. CS101",
        key="cam_sid",
        help="Must be unique.",
    )
    name_cam = cc2.text_input(
        "Full Name *",
        placeholder="e.g. Jane Doe",
        key="cam_name",
    )

    cc3, cc4 = st.columns(2)
    roll_no_cam = cc3.text_input(
        "Roll No *",
        placeholder="e.g. 21CS045",
        key="cam_roll",
        help="Used in parent alert messages.",
    )
    class_section_cam = cc4.text_input(
        "Class / Section *",
        placeholder="e.g. CSE-A",
        key="cam_section",
    )

    st.divider()

    # ── Capture interface — 3 angles side by side ─────────────────────────────
    ANGLES = [
        ("cam_front", "front",         "📷 Front-Facing", "required",    "Look directly at the camera."),
        ("cam_left",  "left_profile",  "◀️ Left Profile",  "recommended", "Turn your head ~45–90° to your left."),
        ("cam_right", "right_profile", "▶️ Right Profile", "recommended", "Turn your head ~45–90° to your right."),
    ]

    angle_cols = st.columns(3)

    for col, (state_key, angle_id, label, req_label, instruction) in zip(angle_cols, ANGLES):
        with col:
            # Badge: required / recommended
            badge_color = "🔴" if req_label == "required" else "🟡"
            st.markdown(f"#### {label}")
            st.caption(f"{badge_color} {req_label.capitalize()} · {instruction}")

            # Camera input widget
            cam_img = st.camera_input(
                f"Capture {label}",
                key=f"widget_{state_key}",
                help=instruction,
            )

            # When user snaps — store in session_state
            if cam_img is not None:
                st.session_state[state_key] = cam_img.getvalue()

            # Show stored capture status
            stored = st.session_state.get(state_key)
            if stored is not None:
                img_bgr = _decode_bytes(stored)
                if img_bgr is not None:
                    st.image(
                        cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB),
                        caption=f"✅ {label} captured",
                        use_container_width=True,
                    )
                    _validation_badge(img_bgr)

                    # Option to retake
                    if st.button(f"🔄 Retake {label}", key=f"retake_{state_key}"):
                        st.session_state.pop(state_key, None)
                        st.rerun()
            else:
                st.caption("_No photo captured yet_")

    st.divider()

    # ── Captured summary ──────────────────────────────────────────────────────
    captured_angles = {
        angle_id: st.session_state.get(state_key)
        for state_key, angle_id, *_ in ANGLES
        if st.session_state.get(state_key) is not None
    }

    n_captured = len(captured_angles)
    front_captured = st.session_state.get("cam_front") is not None

    if n_captured == 0:
        st.info("Capture at least **Front + one Profile** photo above before enrolling.", icon="📷")
    elif n_captured == 1 and not front_captured:
        st.warning("Front-facing photo is required. Please capture it.", icon="⚠️")
    elif n_captured < 2:
        st.warning(
            f"**{n_captured}/3** angle(s) captured.  "
            "At least 2 angles (front + one profile) are required for robust recognition.",
            icon="⚠️",
        )
    else:
        st.success(
            f"**{n_captured}/3** angle(s) ready: "
            + ", ".join(lbl.split(" ", 1)[-1] for lbl in [
                label for state_key, angle_id, label, *_ in ANGLES
                if st.session_state.get(state_key) is not None
            ]),
            icon="✅",
        )

    # ── Enroll button ─────────────────────────────────────────────────────────
    enroll_cam_disabled = (
        n_captured < 2 or
        not front_captured or
        not student_id_cam.strip() or
        not name_cam.strip() or
        not roll_no_cam.strip() or
        not class_section_cam.strip()
    )

    if st.button(
        "🎓 Enroll with Captured Photos",
        key="cam_enroll_btn",
        type="primary",
        use_container_width=True,
        disabled=enroll_cam_disabled,
    ):
        # Build angle-image pairs from session state
        cam_pairs = []
        for state_key, angle_id, *_ in ANGLES:
            raw = st.session_state.get(state_key)
            if raw is not None:
                img_bgr = _decode_bytes(raw)
                if img_bgr is not None:
                    cam_pairs.append((angle_id, img_bgr))

        _submit_enrollment(
            student_id_cam, name_cam, cam_pairs,
            roll_no=roll_no_cam, class_section=class_section_cam,
        )

    # Helper tips
    with st.expander("💡 Tips for better camera enrollment", expanded=False):
        st.markdown(
            """
            **Lighting**
            - Face a window or well-lit wall — avoid strong backlighting.
            - Even indoor lighting gives the best embedding quality.

            **Front-Facing Shot**
            - Look straight into the camera lens.
            - Keep a neutral expression (or slight smile — both work).
            - Hair should not cover eyes or forehead.

            **Profile Shots**
            - Rotate your head ~45–90° to the side.
            - The ear and side of the face should be fully visible.
            - Avoid turning so far that only the back of the head is visible.

            **Distance**
            - Sit ~50–80 cm from the camera (arm's length).
            - Face should fill roughly 40–60% of the frame.

            **Why 3 angles?**
            - In a classroom, students rarely look directly at the camera.
            - Storing front + left + right profile allows the recognizer to
              match whichever pose the student happens to be in during the scan.
            """
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Manage Students
# ═══════════════════════════════════════════════════════════════════════════════
with tab_manage:
    st.markdown("### Enrolled Students")

    students = get_all_students()

    if not students:
        st.info(
            "No students enrolled yet.  "
            "Use the **Upload Photos** or **Live Camera** tab to add students.",
            icon="ℹ️",
        )
    else:
        st.markdown(f"**{len(students)} student(s) enrolled**")

        # Search filter
        search = st.text_input("🔍 Filter by name or ID", placeholder="Search…", key="manage_search")

        filtered = [
            s for s in students
            if not search or
               search.lower() in s["name"].lower() or
               search.lower() in s["student_id"].lower() or
               search.lower() in s.get("roll_no", "").lower()
        ]

        if not filtered:
            st.info("No students match your search.")

        for student in filtered:
            with st.container(border=True):
                c_info, c_angles, c_tg, c_action = st.columns([3, 3, 2, 2])

                with c_info:
                    st.markdown(f"**{student['name']}**")
                    st.caption(f"ID: `{student['student_id']}`")
                    st.caption(f"Roll No: `{student.get('roll_no', '—')}`")
                    st.caption(f"Section: `{student.get('class_section', '—')}`")
                    enrolled_on = student.get("enrolled_on")
                    if enrolled_on:
                        st.caption(
                            f"Enrolled: {enrolled_on.strftime('%Y-%m-%d') if hasattr(enrolled_on, 'strftime') else str(enrolled_on)}"
                        )

                with c_angles:
                    angles = [enc["angle"] for enc in student.get("face_encodings", [])]
                    st.markdown("**Enrolled angles:**")
                    angle_badges = {
                        "front":         "🟢 Front",
                        "left_profile":  "🔵 Left Profile",
                        "right_profile": "🟣 Right Profile",
                        "tilt_up":       "🟡 Tilt Up",
                        "tilt_down":     "🟠 Tilt Down",
                    }
                    for angle in angles:
                        st.markdown(f"- {angle_badges.get(angle, angle)}")

                    if len(angles) < 2:
                        st.warning(
                            "Only 1 angle stored — recognition may be poor for turned heads.",
                            icon="⚠️",
                        )

                with c_tg:
                    st.markdown("**Parent Telegram:**")
                    chat_id = student.get("parent_telegram_chat_id")
                    if chat_id:
                        st.success(f"✅ Linked", icon="📲")
                        st.caption(f"chat_id: `{chat_id}`")
                    else:
                        st.warning("⏳ Not linked", icon="📲")
                        # Show deep link for quick sharing
                        bot_user = _cfg.TELEGRAM_BOT_USERNAME
                        link = f"https://t.me/{bot_user}?start={student['student_id']}"
                        st.markdown(f"[Share link]({link})")

                with c_action:
                    delete_key  = f"delete_{student['student_id']}"
                    confirm_key = f"confirm_{student['student_id']}"

                    if st.button("🗑 Delete", key=delete_key, type="secondary"):
                        st.session_state[confirm_key] = True

                    if st.session_state.get(confirm_key):
                        st.warning("Are you sure? This removes all attendance records too.")
                        c_yes, c_no = st.columns(2)
                        if c_yes.button("Yes, delete", key=f"yes_{student['student_id']}", type="primary"):
                            delete_student(student["student_id"])
                            st.success(f"Deleted {student['name']}.")
                            del st.session_state[confirm_key]
                            st.rerun()
                        if c_no.button("Cancel", key=f"no_{student['student_id']}"):
                            del st.session_state[confirm_key]
                            st.rerun()
