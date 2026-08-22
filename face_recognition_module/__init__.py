"""
face_recognition_module/__init__.py
Exposes the core pipeline functions at package level.
"""

from .detector    import load_detector, detect_faces
from .recognizer  import recognize_faces
from .enroll      import enroll_student
from .encodings_store import load_known_students, cosine_distance

__all__ = [
    "load_detector",
    "detect_faces",
    "recognize_faces",
    "enroll_student",
    "load_known_students",
    "cosine_distance",
]
