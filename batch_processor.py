"""
batch_processor.py
====================
Tiling-based high-resolution classroom image processor.

Why tiling instead of directly running the detector on the full image?
-----------------------------------------------------------------------
RetinaFace (via InsightFace) is trained on images around 640×640 px.
A real classroom photo is typically 3000–6000 px wide.  Passing the full
image directly downscales the internal feature maps, making small/distant
faces (students at the back of the room) fall below the detection threshold.

Tiling approach:
  1. Split the full-resolution image into overlapping tiles (default 640×640
     with 80 px overlap between adjacent tiles).
  2. Run the detector on each tile independently at full tile resolution.
  3. Map each tile-local bounding box back to full-image coordinates.
  4. Merge / deduplicate overlapping detections across tile boundaries using
     a Non-Maximum Suppression (NMS) based on Intersection over Union (IoU).
  5. Pass the deduplicated face list to recognizer.recognize_faces().

This is the primary processing path for 50–60 student classroom scans.
Live per-frame webcam mode (video_processor.py) is for small groups only.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import cv2
import numpy as np

import config
from face_recognition_module.detector import detect_faces
from face_recognition_module.recognizer import recognize_faces, draw_recognition_results
from face_recognition_module.encodings_store import load_known_students
from database.db_operations import mark_attendance_if_new

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tiling
# ─────────────────────────────────────────────────────────────────────────────

def tile_image(
    image: np.ndarray,
    tile_size: int = config.TILE_SIZE,
    overlap: int = config.TILE_OVERLAP,
) -> list[tuple[np.ndarray, tuple[int, int, int, int]]]:
    """
    Split a large image into overlapping tiles.

    Parameters
    ----------
    image     : Full-resolution BGR image.
    tile_size : Width and height of each tile (square).
    overlap   : Number of pixels to overlap between adjacent tiles.

    Returns
    -------
    List of (tile_image, (x_offset, y_offset, tile_w, tile_h)) tuples.
    tile_image is a crop of `image`; offsets are in full-image coordinates.
    """
    h, w = image.shape[:2]
    stride = tile_size - overlap
    tiles = []

    y = 0
    while y < h:
        x = 0
        while x < w:
            x2 = min(x + tile_size, w)
            y2 = min(y + tile_size, h)
            tile = image[y:y2, x:x2]
            tiles.append((tile, (x, y, x2 - x, y2 - y)))
            if x2 == w:
                break
            x += stride
        if y2 == h:
            break
        y += stride

    logger.debug("Tiled %dx%d image into %d tiles (size=%d, overlap=%d).", w, h, len(tiles), tile_size, overlap)
    return tiles


# ─────────────────────────────────────────────────────────────────────────────
# Detection on tiles → global coordinates
# ─────────────────────────────────────────────────────────────────────────────

def detect_on_tiles(
    tiles: list[tuple[np.ndarray, tuple[int, int, int, int]]],
) -> list[dict]:
    """
    Run face detection on every tile and remap bounding boxes to full-image
    coordinate space.

    Returns
    -------
    Flat list of detection dicts (same schema as detector.detect_faces()),
    with bounding boxes in full-image coordinates.
    """
    all_detections = []

    for tile_img, (x_off, y_off, _tw, _th) in tiles:
        tile_dets = detect_faces(tile_img)
        for det in tile_dets:
            # Remap bbox to full-image coordinates
            tx1, ty1, tx2, ty2 = det["bbox"]
            det["bbox"] = [
                tx1 + x_off,
                ty1 + y_off,
                tx2 + x_off,
                ty2 + y_off,
            ]
            all_detections.append(det)

    logger.debug("Total raw detections across all tiles: %d", len(all_detections))
    return all_detections


# ─────────────────────────────────────────────────────────────────────────────
# IoU-based Non-Maximum Suppression (deduplication)
# ─────────────────────────────────────────────────────────────────────────────

def _iou(box_a: list[int], box_b: list[int]) -> float:
    """Compute Intersection over Union of two [x1,y1,x2,y2] boxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter   = inter_w * inter_h

    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union  = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def merge_detections_iou(
    detections: list[dict],
    iou_threshold: float = config.IOU_THRESHOLD,
) -> list[dict]:
    """
    Remove duplicate detections that arise from the same face appearing in
    multiple overlapping tiles.  Uses a greedy NMS approach:

    1. Sort detections by detector confidence (highest first).
    2. Greedily select the top detection and suppress any remaining detection
       whose IoU with the selected box exceeds iou_threshold.
    3. Repeat until no detections remain.

    This is equivalent to standard NMS used in object detection pipelines.

    Parameters
    ----------
    detections    : Flat list of detections in full-image coordinates.
    iou_threshold : IoU above which two boxes are considered the same face.

    Returns
    -------
    Deduplicated list of detections (higher-confidence box kept).
    """
    if not detections:
        return []

    # Sort by confidence descending
    sorted_dets = sorted(detections, key=lambda d: d.get("det_score", 0.0), reverse=True)
    kept = []
    suppressed = set()

    for i, det in enumerate(sorted_dets):
        if i in suppressed:
            continue
        kept.append(det)
        for j in range(i + 1, len(sorted_dets)):
            if j in suppressed:
                continue
            iou_val = _iou(det["bbox"], sorted_dets[j]["bbox"])
            if iou_val > iou_threshold:
                suppressed.add(j)

    logger.debug(
        "NMS: %d raw → %d after dedup (iou_threshold=%.2f).",
        len(detections), len(kept), iou_threshold,
    )
    return kept


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def process_classroom_image(
    image_source: Union[str, Path, np.ndarray],
    known_students: list[dict] | None = None,
    threshold: float | None = None,
    commit_attendance: bool = False,
    session: str = "FN",
) -> dict:
    """
    Full pipeline: load → tile → detect → dedup → recognise → (optionally mark attendance).

    Parameters
    ----------
    image_source      : File path (str/Path) or a pre-loaded BGR numpy array.
    known_students    : Pre-loaded gallery; if None, loaded from MongoDB.
    threshold         : Recognition threshold; defaults to config.RECOGNITION_THRESHOLD.
    commit_attendance : If True, call mark_attendance_if_new for each recognised student.
    session           : "FN" (Forenoon) or "AN" (Afternoon) — determines which
                        session record is written.  Defaults to "FN" for backward
                        compatibility with callers that pre-date Phase 9.

    Returns
    -------
    {
        "annotated_image" : np.ndarray  — full-res image with boxes + labels drawn,
        "detections"      : list[dict]  — deduplicated raw detections,
        "results"         : list[dict]  — recognition results (parallel to detections),
        "n_detected"      : int,
        "n_recognised"    : int,
        "n_unknown"       : int,
        "attendance_new"  : list[str]   — student_ids newly marked (if commit_attendance),
        "session"         : str         — echoed back for the UI to use,
        "error"           : str | None,
    }
    """
    # ── Load image ─────────────────────────────────────────────────────────────
    if isinstance(image_source, (str, Path)):
        image = cv2.imread(str(image_source))
        if image is None:
            return _error_result(f"Could not read image from: {image_source}")
    else:
        image = image_source

    if image is None or image.size == 0:
        return _error_result("Received an empty image.")

    h, w = image.shape[:2]
    logger.info("Processing classroom image: %dx%d px.", w, h)

    # ── Load gallery ───────────────────────────────────────────────────────────
    if known_students is None:
        known_students = load_known_students()

    if not known_students:
        logger.warning("No students enrolled — detection will proceed but all faces will be 'Unknown'.")

    # ── Tile → detect → remap ──────────────────────────────────────────────────
    tiles           = tile_image(image)
    raw_detections  = detect_on_tiles(tiles)

    # ── Extra full-image pass at reduced resolution (catches tile-boundary faces)
    # Resize to at most 1280 on the longer side, run detection, scale bboxes back.
    _max_side = 1280
    _scale = min(1.0, _max_side / max(h, w))
    if _scale < 1.0:
        _small = cv2.resize(image, (int(w * _scale), int(h * _scale)), interpolation=cv2.INTER_AREA)
    else:
        _small = image
    _full_dets = detect_faces(_small)
    for _d in _full_dets:
        bx1, by1, bx2, by2 = _d["bbox"]
        _d["bbox"] = [
            int(bx1 / _scale), int(by1 / _scale),
            int(bx2 / _scale), int(by2 / _scale),
        ]
    raw_detections.extend(_full_dets)
    logger.info("Full-image pass added %d extra detections. Total raw: %d", len(_full_dets), len(raw_detections))

    if not raw_detections:
        return {
            "annotated_image": image,
            "detections":      [],
            "results":         [],
            "n_detected":      0,
            "n_recognised":    0,
            "n_unknown":       0,
            "attendance_new":  [],
            "session":         session,
            "error": (
                "No faces detected in this image. "
                "Check that the image is well-lit, high-resolution, and faces are visible. "
                f"Image size: {w}×{h} px | Tiles processed: {len(tiles)}"
            ),
        }

    # ── Deduplicate across tile boundaries ────────────────────────────────────
    deduped = merge_detections_iou(raw_detections)
    logger.info("Faces after NMS: %d (from %d raw).", len(deduped), len(raw_detections))

    # ── Recognise ─────────────────────────────────────────────────────────────
    results = recognize_faces(deduped, known_students, threshold=threshold)

    # ── Annotate image ─────────────────────────────────────────────────────────
    annotated = draw_recognition_results(image, results)

    # ── Optionally mark attendance ────────────────────────────────────────────
    attendance_new: list[str] = []
    if commit_attendance:
        for res in results:
            if res["student_id"] != "Unknown":
                # Fetch denormalised fields for the attendance record
                from database.db_operations import get_student_by_id as _get_stu
                stu = _get_stu(res["student_id"]) or {}
                inserted = mark_attendance_if_new(
                    student_id=res["student_id"],
                    name=res["name"],
                    matched_angle=res["matched_angle"],
                    match_distance=res["distance"],
                    session=session,
                    roll_no=stu.get("roll_no", res["student_id"]),
                    class_section=stu.get("class_section", ""),
                )
                if inserted:
                    attendance_new.append(res["student_id"])

    n_recognised = sum(1 for r in results if r["student_id"] != "Unknown")
    n_unknown    = len(results) - n_recognised

    return {
        "annotated_image": annotated,
        "detections":      deduped,
        "results":         results,
        "n_detected":      len(deduped),
        "n_recognised":    n_recognised,
        "n_unknown":       n_unknown,
        "attendance_new":  attendance_new,
        "session":         session,
        "error":           None,
    }


def _error_result(msg: str) -> dict:
    return {
        "annotated_image": None,
        "detections":      [],
        "results":         [],
        "n_detected":      0,
        "n_recognised":    0,
        "n_unknown":       0,
        "attendance_new":  [],
        "session":         "",
        "error":           msg,
    }
