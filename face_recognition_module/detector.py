"""
face_recognition_module/detector.py
=====================================
Wraps InsightFace's FaceAnalysis (buffalo_l model pack) for face detection
and embedding extraction.

Why InsightFace + buffalo_l instead of classic dlib/face_recognition?
----------------------------------------------------------------------
• The detector inside buffalo_l is RetinaFace — a multi-scale, anchor-based
  face detector that is specifically trained to find many small faces in a
  single wide image and handles significant yaw/pitch (turned heads, side
  profiles) far better than dlib's HOG/CNN detector, which was tuned for
  single near-frontal faces.

• The embedding model is ArcFace (512-d).  ArcFace is more discriminative
  under pose and lighting variation than dlib's 128-d Euclidean embeddings
  because its loss function explicitly maximises inter-class angular margin
  across a large identity dataset.

• Both components run acceptably on CPU for classroom-scale batch frames.
  A few seconds per high-resolution snapshot is an acceptable and intentional
  tradeoff for higher recall — we do NOT sacrifice detection quality for speed.

Fallback order (see project README) if insightface cannot be installed:
  1. YOLOv8-face (ultralytics) + deepface ArcFace embeddings
  2. Classic face_recognition (dlib) — multi-angle/small-face recall will
     be noticeably worse, especially for distant or turned faces.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

import config

logger = logging.getLogger(__name__)

# ── Module-level singleton ─────────────────────────────────────────────────────
# Stored at module level (not inside a function) so that Streamlit's
# st.cache_resource wrapper in app.py can hold the single instance.
_face_app = None


def load_detector():
    """
    Initialise and return the InsightFace FaceAnalysis app.

    Loads the buffalo_l model pack which contains:
      • det_10g   — RetinaFace multi-face detector
      • w600k_r50 — ArcFace ResNet-50 recognition model

    The models auto-download (~500 MB) on the first call if not cached locally.
    Subsequent calls use the cached copy in ~/.insightface/models/buffalo_l/.

    Returns
    -------
    insightface.app.FaceAnalysis instance, ready for inference.

    Raises
    ------
    RuntimeError if insightface or onnxruntime cannot be imported/initialised.
    """
    global _face_app
    if _face_app is not None:
        return _face_app

    try:
        import insightface
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name=config.INSIGHTFACE_MODEL,
            allowed_modules=["detection", "recognition"],
        )
        # det_size controls the internal resize for the detection head.
        # (640, 640) is the canonical size for RetinaFace and handles most
        # classroom tile sizes well.  The batch_processor.py splits large images
        # into tiles of this size, so we do NOT downscale full classroom images
        # before detection — that would be the #1 cause of missed small faces.
        app.prepare(ctx_id=config.CTX_ID, det_size=(640, 640), det_thresh=0.35)

        _face_app = app
        logger.info("InsightFace (buffalo_l) loaded successfully.")
        return _face_app

    except ImportError as exc:
        raise RuntimeError(
            "insightface or onnxruntime could not be imported. "
            "Install with:  pip install insightface onnxruntime\n"
            f"Original error: {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"InsightFace failed to initialise: {exc}\n"
            "Ensure onnxruntime (CPU build) is installed and that the model "
            "buffalo_l has been downloaded (internet required once)."
        ) from exc


def detect_faces(frame: np.ndarray) -> list[dict]:
    """
    Run face detection + embedding extraction on a single BGR image.

    IMPORTANT: Do NOT pass a downscaled version of the classroom image here.
    Use batch_processor.py (tiling approach) so that the detector operates at
    full resolution — downscaling is the #1 cause of missed small/distant faces.

    Parameters
    ----------
    frame : np.ndarray
        BGR image as returned by cv2.imread or cv2.VideoCapture.read().
        Any resolution is accepted; tiling is handled upstream.

    Returns
    -------
    List of detection dicts, one per face:
    {
        "bbox"      : [x1, y1, x2, y2]  (ints, pixel coordinates),
        "landmarks" : np.ndarray of shape (5, 2),
        "embedding" : np.ndarray of shape (512,)  — L2-normalised ArcFace,
        "det_score" : float  — detector confidence [0, 1],
    }
    An empty list is returned if no faces are detected.
    """
    app = load_detector()

    if frame is None or frame.size == 0:
        logger.warning("detect_faces received an empty frame — skipping.")
        return []

    try:
        faces = app.get(frame)
    except Exception as exc:
        logger.error("InsightFace inference error: %s", exc)
        return []

    results = []
    for face in faces:
        bbox = face.bbox.astype(int).tolist()   # [x1, y1, x2, y2]
        h = bbox[3] - bbox[1]
        if h < config.MIN_FACE_SIZE_PX:
            # Skip sub-pixel or extremely tiny detections (usually false positives)
            continue

        embedding = getattr(face, "embedding", None)
        if embedding is None:
            # Embedding can be None if the recognition model failed internally.
            logger.debug("Face detected but embedding is None — skipping.")
            continue

        results.append({
            "bbox":       bbox,
            "landmarks":  face.kps if face.kps is not None else np.zeros((5, 2)),
            "embedding":  np.array(embedding, dtype=np.float32),
            "det_score":  float(face.det_score),
        })

    logger.debug("detect_faces: %d face(s) found.", len(results))
    return results


def draw_detections(
    frame: np.ndarray,
    detections: list[dict],
    labels: Optional[list[str]] = None,
    color: tuple = (0, 255, 128),
) -> np.ndarray:
    """
    Draw bounding boxes (and optional name labels) on a copy of the frame.

    Parameters
    ----------
    frame      : BGR image (original, not modified in-place)
    detections : Output of detect_faces()
    labels     : List of strings, same length as detections.  Pass None for
                 unlabelled boxes (detection-only visualisation).
    color      : BGR colour for the box outline

    Returns
    -------
    Annotated BGR image (copy).
    """
    import cv2

    out = frame.copy()
    for idx, det in enumerate(detections):
        x1, y1, x2, y2 = det["bbox"]
        score = det.get("det_score", 0.0)

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        label_text = labels[idx] if labels else f"{score:.2f}"
        cv2.putText(
            out, label_text,
            (x1, max(y1 - 8, 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
        )

    return out
