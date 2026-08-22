"""
routers/recognition.py
=======================
POST /recognize — accept a JPEG image, run InsightFace, return detected names + bboxes.
The Flutter app sends frames here every ~2 seconds during live scan.
"""

import io
import numpy as np
import cv2

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from face_recognition_module.detector import detect_faces
from face_recognition_module.recognizer import recognize_faces
from face_recognition_module.encodings_store import load_known_students
from dependencies import require_role, TokenData
from models.recognition import RecognizeResponse, RecognitionResult

router = APIRouter()

# Cache the student gallery in memory — reload only on explicit request
_gallery_cache: list[dict] | None = None


def _get_gallery() -> list[dict]:
    global _gallery_cache
    if _gallery_cache is None:
        _gallery_cache = load_known_students()
    return _gallery_cache


@router.post("/reload-gallery")
async def reload_gallery(current_user: TokenData = Depends(require_role("teacher", "admin"))):
    """Force reload of the in-memory student gallery (call after enrolling a new student)."""
    global _gallery_cache
    _gallery_cache = None
    students = _get_gallery()
    return {"message": f"Gallery reloaded. {len(students)} students loaded."}


@router.post("", response_model=RecognizeResponse)
async def recognize(
    image: UploadFile = File(..., description="JPEG/PNG image from the camera"),
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """
    Run face detection + recognition on an uploaded image.

    The Flutter Live Scan screen captures a frame from the smartboard camera,
    compresses it to JPEG, and POSTs it here as multipart/form-data.

    Returns:
      - results: list of {student_id, name, bbox, distance, det_score, matched_angle}
      - total_detected / total_recognised counts
    """
    # Read uploaded bytes → numpy BGR image
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file.")

    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image. Ensure it is a valid JPEG/PNG.")

    # Detect faces
    detections = detect_faces(frame)

    # Recognise against gallery
    gallery = _get_gallery()
    results = recognize_faces(detections, gallery)

    api_results = [
        RecognitionResult(
            student_id=r["student_id"],
            name=r["name"],
            matched_angle=r["matched_angle"],
            distance=r["distance"],
            det_score=r["det_score"],
            bbox=r["bbox"],
        )
        for r in results
    ]

    n_recognised = sum(1 for r in api_results if r.student_id != "Unknown")
    return RecognizeResponse(
        results=api_results,
        total_detected=len(api_results),
        total_recognised=n_recognised,
    )
