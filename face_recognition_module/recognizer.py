"""
face_recognition_module/recognizer.py
========================================
Multi-angle face recognition against a MongoDB-stored gallery.

Key design: comparing against MULTIPLE ANGLES per student
----------------------------------------------------------
Each enrolled student has 2-3 stored embeddings, one per enrollment angle
(front, left_profile, right_profile, etc.).

When a student is sitting in a classroom and not looking straight at the
camera, their face embedding will be closest to the stored embedding for the
angle that best matches their current pose.  If we stored ONLY a single
front-facing embedding (as classic face_recognition systems do), we would
get high distances (missed matches) for turned heads.

By comparing each detected face against ALL stored angle-embeddings of ALL
students and taking the overall best match, we correctly identify students
regardless of their head pose — this is the recognition-quality lever that
makes EngageLens work in a real classroom.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

import config
from .encodings_store import cosine_distance

logger = logging.getLogger(__name__)


def recognize_faces(
    detections: list[dict],
    known_students: list[dict],
    threshold: Optional[float] = None,
) -> list[dict]:
    """
    Match each detected face against the multi-angle gallery and return
    recognition results.

    Parameters
    ----------
    detections     : List of dicts from detector.detect_faces().
                     Each must contain an "embedding" key (np.ndarray, 512-d).
    known_students : Gallery loaded via encodings_store.load_known_students().
    threshold      : Cosine distance cutoff.  Defaults to config.RECOGNITION_THRESHOLD.
                     Lower → stricter (fewer false positives, more unknowns).
                     Higher → more permissive (more matches, risk of false positives).

    Returns
    -------
    List of result dicts, parallel to `detections`:
    {
        "bbox"          : [x1, y1, x2, y2],
        "student_id"    : str or "Unknown",
        "name"          : str or "Unknown",
        "matched_angle" : str or "N/A",   # which stored angle was closest
        "distance"      : float,           # best cosine distance found
        "det_score"     : float,           # detector confidence
    }

    Why we iterate ALL students × ALL angles:
        For N students with A angles each and D detections:
        time ~ O(D × N × A)
        For a classroom of 60 students × 3 angles × 60 detections ≈ 10 800
        dot products — negligible on CPU (~5 ms total).
    """
    if threshold is None:
        threshold = config.RECOGNITION_THRESHOLD

    if not known_students:
        logger.warning("Gallery is empty — all faces will be 'Unknown'.")
        return [_unknown_result(det) for det in detections]

    results = []
    for det in detections:
        query_emb = det.get("embedding")
        if query_emb is None:
            results.append(_unknown_result(det))
            continue

        best_distance    = float("inf")
        best_student_id  = "Unknown"
        best_name        = "Unknown"
        best_angle       = "N/A"

        # ── Compare against every angle-embedding of every student ──────────
        for student in known_students:
            for enc in student.get("face_encodings", []):
                gallery_emb = enc.get("embedding")
                if gallery_emb is None:
                    continue

                dist = cosine_distance(query_emb, gallery_emb)

                if dist < best_distance:
                    best_distance   = dist
                    best_student_id = student["student_id"]
                    best_name       = student["name"]
                    best_angle      = enc["angle"]

        # ── Apply threshold ─────────────────────────────────────────────────
        if best_distance > threshold:
            best_student_id = "Unknown"
            best_name       = "Unknown"
            best_angle      = "N/A"
            logger.debug(
                "Face at %s → Unknown (best dist=%.4f > threshold=%.4f)",
                det["bbox"], best_distance, threshold,
            )
        else:
            logger.debug(
                "Face at %s → %s (%s) | angle=%s | dist=%.4f",
                det["bbox"], best_name, best_student_id, best_angle, best_distance,
            )

        results.append({
            "bbox":          det["bbox"],
            "student_id":    best_student_id,
            "name":          best_name,
            "matched_angle": best_angle,
            "distance":      round(best_distance, 4),
            "det_score":     det.get("det_score", 0.0),
        })

    n_recognised = sum(1 for r in results if r["student_id"] != "Unknown")
    logger.info(
        "Recognition: %d detected, %d recognised, %d unknown.",
        len(results), n_recognised, len(results) - n_recognised,
    )
    return results


def _unknown_result(det: dict) -> dict:
    """Build a result dict for a face that could not be recognised."""
    return {
        "bbox":          det.get("bbox", [0, 0, 0, 0]),
        "student_id":    "Unknown",
        "name":          "Unknown",
        "matched_angle": "N/A",
        "distance":      float("inf"),
        "det_score":     det.get("det_score", 0.0),
    }


def draw_recognition_results(
    frame: np.ndarray,
    results: list[dict],
) -> np.ndarray:
    """
    Draw labelled bounding boxes showing name, matched angle, and distance.

    Colour coding:
      Green  — recognised student  (solid label background)
      Red    — unknown face        (solid label background)

    Labels are rendered with a solid filled background pill so they remain
    readable on any background (classroom walls, clothing, etc.).
    Font size is scaled relative to the face bounding-box height so labels
    are readable even on very high-resolution images.
    """
    import cv2

    out = frame.copy()
    img_h, img_w = out.shape[:2]

    for res in results:
        x1, y1, x2, y2 = res["bbox"]
        # Clamp to image bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img_w - 1, x2), min(img_h - 1, y2)

        is_known = res["student_id"] != "Unknown"

        # ── Box colour & thickness ─────────────────────────────────────────────
        # Scale thickness proportionally to face size (min 2, max 6)
        face_h = max(y2 - y1, 1)
        thickness = max(2, min(6, face_h // 30))

        if is_known:
            box_color   = (30, 220, 80)    # Bright green
            label_bg    = (20, 140, 50)    # Dark green fill
            label_fg    = (255, 255, 255)  # White text
        else:
            box_color   = (30,  50, 230)   # Bright red
            label_bg    = (20,  30, 170)   # Dark red fill
            label_fg    = (255, 255, 255)  # White text

        cv2.rectangle(out, (x1, y1), (x2, y2), box_color, thickness)

        # ── Scale font to face box height ─────────────────────────────────────
        # 0.45 scale at 40px face height → 0.9 at 80px → capped at 1.5
        font_scale  = max(0.45, min(1.5, face_h / 88.0))
        font        = cv2.FONT_HERSHEY_SIMPLEX
        font_thick  = max(1, int(font_scale * 2))
        line_height = int(font_scale * 28)

        # ── Build label lines ─────────────────────────────────────────────────
        if is_known:
            line1 = res["name"]
            line2 = f"{res['matched_angle']} | {res['distance']:.3f}"
        else:
            line1 = "Unknown"
            line2 = f"conf={res['det_score']:.2f}"

        # ── Measure text to draw solid background pill ────────────────────────
        (w1, h1), _ = cv2.getTextSize(line1, font, font_scale, font_thick)
        (w2, h2), _ = cv2.getTextSize(line2, font, font_scale * 0.75, max(1, font_thick - 1))
        pill_w = max(w1, w2) + 10
        pill_h = h1 + h2 + line_height + 6

        # Place pill above the box; shift down into frame if it goes off-screen
        pill_y1 = y1 - pill_h - 4
        pill_y2 = y1 - 2
        if pill_y1 < 0:
            pill_y1 = y2 + 2
            pill_y2 = y2 + pill_h + 4

        # Draw filled rectangle background
        cv2.rectangle(out, (x1, pill_y1), (x1 + pill_w, pill_y2), label_bg, -1)

        # Optional border on the pill matching box_color
        cv2.rectangle(out, (x1, pill_y1), (x1 + pill_w, pill_y2), box_color, 1)

        # Draw text lines
        text_x = x1 + 5
        cv2.putText(out, line1, (text_x, pill_y1 + h1 + 2),
                    font, font_scale, label_fg, font_thick, cv2.LINE_AA)
        cv2.putText(out, line2, (text_x, pill_y1 + h1 + line_height + 2),
                    font, font_scale * 0.75, label_fg,
                    max(1, font_thick - 1), cv2.LINE_AA)

    return out

