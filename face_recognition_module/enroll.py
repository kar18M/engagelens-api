"""
face_recognition_module/enroll.py
====================================
Multi-angle student enrollment workflow.

Design rationale for multi-angle enrollment:
--------------------------------------------
When a student sits in a classroom and turns their head to listen to a
classmate, look at the board, or check their phone, the face they present
to the camera can differ substantially from a straight-on frontal pose.
A single front-facing embedding will often produce a high cosine distance
(missed match) for poses with > ~30° yaw.

By capturing and storing separate embeddings for front, left_profile, and
right_profile at enrollment time, the recognizer can match against whichever
stored angle is closest to the student's current head pose in the classroom
shot.  This is the enrollment-side key to EngageLens's robust recognition.

Requirements enforced here:
  • At least 2 angles must be provided (front + any one profile minimum).
  • Each enrollment image must contain EXACTLY ONE face.
    - Zero faces   → image is too blurry, dark, or the face is out-of-frame.
    - Multiple     → image shows multiple people; the system can't know which
                     embedding to store.
  • Photos are saved locally to data/enrolled_faces/{student_id}/ for
    human audit and re-enrollment without needing to re-upload.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import cv2
import numpy as np

import config
from .detector import detect_faces

logger = logging.getLogger(__name__)


def enroll_student(
    student_id: str,
    name: str,
    angle_image_pairs: list[tuple[str, np.ndarray]],
) -> tuple[bool, list[dict], list[str]]:
    """
    Process enrollment images, extract per-angle embeddings, and save photos.

    Parameters
    ----------
    student_id         : Unique identifier, e.g. "CS101"
    name               : Human-readable student name
    angle_image_pairs  : List of (angle_str, bgr_numpy_image) tuples.
                         angle_str must be one of config.VALID_ANGLES.
                         Provide at least config.MIN_ENROLLMENT_ANGLES entries.

    Returns
    -------
    (success, angle_embeddings, errors)
      success          : True if all images passed validation
      angle_embeddings : List of dicts for database.insert_student():
                         [{"angle": str, "embedding": np.ndarray, "photo_path": str}, ...]
      errors           : List of human-readable error strings (empty on success)
    """
    errors: list[str] = []
    angle_embeddings: list[dict] = []

    # ── Validate number of angles ──────────────────────────────────────────────
    if len(angle_image_pairs) < config.MIN_ENROLLMENT_ANGLES:
        errors.append(
            f"You must provide at least {config.MIN_ENROLLMENT_ANGLES} enrollment angles "
            f"(front + at least one profile).  "
            f"Got {len(angle_image_pairs)}.  "
            "Multi-angle enrollment is mandatory for robust recognition of turned heads "
            "in classroom photos."
        )
        return False, [], errors

    # ── Validate angle names ───────────────────────────────────────────────────
    for angle, _ in angle_image_pairs:
        if angle not in config.VALID_ANGLES:
            errors.append(f"Invalid angle '{angle}'. Must be one of: {config.VALID_ANGLES}")
    if errors:
        return False, [], errors

    # ── Create output directory ────────────────────────────────────────────────
    student_dir = config.ENROLLED_FACES_DIR / student_id
    student_dir.mkdir(parents=True, exist_ok=True)

    # ── Process each angle ─────────────────────────────────────────────────────
    for angle, image in angle_image_pairs:
        result = _process_single_angle(image, angle, student_id, student_dir)
        if result["error"]:
            errors.append(f"[{angle}] {result['error']}")
        else:
            angle_embeddings.append({
                "angle":      angle,
                "embedding":  result["embedding"],
                "photo_path": result["photo_path"],
            })

    if errors:
        # Clean up any partially saved photos
        if student_dir.exists():
            shutil.rmtree(student_dir, ignore_errors=True)
        return False, [], errors

    logger.info(
        "Enrollment successful for %s (%s): %d angle(s) stored.",
        name, student_id, len(angle_embeddings),
    )
    return True, angle_embeddings, []


def _process_single_angle(
    image: np.ndarray,
    angle: str,
    student_id: str,
    output_dir: Path,
) -> dict:
    """
    Run detection on a single enrollment image and return the embedding + path.

    Returns a dict with keys:
      embedding  : np.ndarray | None
      photo_path : str
      error      : str | None  (None on success)
    """
    if image is None or image.size == 0:
        return {"embedding": None, "photo_path": "", "error": "Image is empty or could not be read."}

    detections = detect_faces(image)

    if len(detections) == 0:
        return {
            "embedding":  None,
            "photo_path": "",
            "error": (
                "No face detected in this photo. "
                "Ensure the face is clearly visible, well-lit, and not obscured. "
                "For profile shots, make sure the full side of the face is in frame."
            ),
        }

    if len(detections) > 1:
        return {
            "embedding":  None,
            "photo_path": "",
            "error": (
                f"{len(detections)} faces detected in this photo. "
                "Enrollment photos must contain exactly one person. "
                "Please upload a photo with only the student being enrolled."
            ),
        }

    # Exactly one face — extract embedding
    embedding = detections[0]["embedding"]

    # Save photo copy
    photo_filename = f"{angle}.jpg"
    photo_path = output_dir / photo_filename
    cv2.imwrite(str(photo_path), image)
    relative_path = str(photo_path.relative_to(config.BASE_DIR))

    logger.debug("Saved enrollment photo: %s", photo_path)

    return {
        "embedding":  embedding,
        "photo_path": relative_path,
        "error":      None,
    }


def validate_enrollment_image(image: np.ndarray) -> tuple[bool, str]:
    """
    Quick validation check for a single uploaded enrollment image.
    Returns (is_valid, message) — useful for live preview feedback in Streamlit.
    """
    if image is None or image.size == 0:
        return False, "Image could not be decoded."

    detections = detect_faces(image)
    n = len(detections)

    if n == 0:
        return False, "No face detected. Please use a clearer, well-lit photo."
    if n > 1:
        return False, f"{n} faces detected. Please upload a photo with only one person."

    score = detections[0].get("det_score", 0)
    if score < 0.7:
        return True, f"⚠ Face detected but confidence is low ({score:.2f}). Consider a higher-quality photo."

    return True, f"✓ Face detected (confidence {score:.2f})"
