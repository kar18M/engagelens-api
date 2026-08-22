"""
routers/enroll.py
==================
POST /enroll — enroll a new student with multi-angle face photos.

Accepts multipart form data with:
  - student_id, name, roll_no, class_section (form fields)
  - front, left_profile, right_profile, etc. (file uploads, one per angle)

At least 2 angle images are required.
"""

import io
import numpy as np
import cv2
from typing import Optional

from fastapi import APIRouter, Form, UploadFile, File, Depends, HTTPException, status

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from face_recognition_module.enroll import enroll_student
from database.db_operations import insert_student, get_student_by_id
from dependencies import require_role, TokenData
from models.recognition import EnrollResponse
import config

router = APIRouter()


async def _decode_image(upload: UploadFile) -> Optional[np.ndarray]:
    """Decode an uploaded file to a BGR numpy array. Returns None on failure."""
    contents = await upload.read()
    if not contents:
        return None
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return frame


@router.post("", response_model=EnrollResponse)
async def enroll(
    student_id: str = Form(...),
    name: str = Form(...),
    roll_no: str = Form(""),
    class_section: str = Form(""),
    parent_telegram_chat_id: Optional[str] = Form(None),
    # Accept up to 5 angle images
    front: Optional[UploadFile] = File(None),
    left_profile: Optional[UploadFile] = File(None),
    right_profile: Optional[UploadFile] = File(None),
    tilt_up: Optional[UploadFile] = File(None),
    tilt_down: Optional[UploadFile] = File(None),
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """
    Enroll a student with multi-angle face photos.
    Requires at least 2 uploaded angle images.
    """
    # Check if student already enrolled
    if get_student_by_id(student_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student '{student_id}' is already enrolled. Delete first to re-enroll.",
        )

    # Build angle-image pairs from uploaded files
    angle_image_pairs: list[tuple[str, np.ndarray]] = []
    angle_file_map = {
        "front": front,
        "left_profile": left_profile,
        "right_profile": right_profile,
        "tilt_up": tilt_up,
        "tilt_down": tilt_down,
    }

    for angle_name, file_upload in angle_file_map.items():
        if file_upload is not None and file_upload.filename:
            img = await _decode_image(file_upload)
            if img is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not decode image for angle '{angle_name}'. Ensure it is a valid JPEG/PNG.",
                )
            angle_image_pairs.append((angle_name, img))

    if len(angle_image_pairs) < config.MIN_ENROLLMENT_ANGLES:
        raise HTTPException(
            status_code=400,
            detail=f"At least {config.MIN_ENROLLMENT_ANGLES} angle images are required. Got {len(angle_image_pairs)}.",
        )

    # Run enrollment pipeline
    success, angle_embeddings, errors = enroll_student(student_id, name, angle_image_pairs)

    if not success:
        return EnrollResponse(success=False, message="Enrollment failed.", errors=errors)

    # Insert into database
    inserted = insert_student(
        student_id=student_id,
        name=name,
        angle_embeddings=angle_embeddings,
        roll_no=roll_no,
        class_section=class_section,
        parent_telegram_chat_id=parent_telegram_chat_id,
    )

    if not inserted:
        return EnrollResponse(
            success=False,
            message=f"Student '{student_id}' already exists in database.",
            errors=["Duplicate student_id."],
        )

    angles_done = [ae["angle"] for ae in angle_embeddings]
    return EnrollResponse(
        success=True,
        message=f"Student '{name}' ({student_id}) enrolled successfully with {len(angles_done)} angle(s).",
        angles_enrolled=angles_done,
    )
