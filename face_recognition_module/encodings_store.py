"""
face_recognition_module/encodings_store.py
===========================================
Helper utilities for:
  • Loading the known-students gallery from MongoDB (for the recognizer)
  • Cosine distance computation used by the recognizer
  • L2-normalisation of embeddings

Keeping these functions separate avoids circular imports between recognizer.py
and db_operations.py.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


# ── Distance Utilities ─────────────────────────────────────────────────────────

def l2_normalize(vec: np.ndarray) -> np.ndarray:
    """
    Return the L2-normalised version of a vector.
    InsightFace's ArcFace already outputs normalised embeddings, but we
    normalise again defensively in case embeddings were stored after any
    transformation.
    """
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine distance between two embedding vectors.

    Returns
    -------
    float in [0, 2]:
      0   — identical direction (same person, ideal)
      1   — orthogonal
      2   — opposite direction (maximally different)

    A threshold of 0.45 (config.RECOGNITION_THRESHOLD) means:
      distance < 0.45 → same person
      distance ≥ 0.45 → unknown

    Lower distance = better match.
    """
    a_n = l2_normalize(a.astype(np.float32))
    b_n = l2_normalize(b.astype(np.float32))
    # Cosine similarity ∈ [-1, 1]; distance = 1 - similarity ∈ [0, 2]
    similarity = float(np.dot(a_n, b_n))
    return 1.0 - similarity


def load_known_students() -> list[dict]:
    """
    Load all enrolled students from MongoDB and return a gallery list
    ready for use in recognizer.recognize_faces().

    Each element:
    {
        "student_id":     str,
        "name":           str,
        "face_encodings": [
            {"angle": str, "embedding": np.ndarray(512,)},
            ...
        ],
    }

    Returns an empty list (not an error) if no students are enrolled yet.
    """
    from database.db_operations import get_all_students  # local import to avoid circular

    try:
        students = get_all_students()
        logger.info("Gallery loaded: %d student(s).", len(students))
        return students
    except Exception as exc:
        logger.error("Failed to load known students from MongoDB: %s", exc)
        return []
