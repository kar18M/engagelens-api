"""
video_processor.py
====================
Lightweight live-mode video processor for SMALL groups (study rooms, small
seminars — NOT full 50-60 student classrooms).

For full-classroom attendance, use batch_processor.process_classroom_image()
via the Batch Classroom Scan page instead, which tiles the high-res snapshot
for superior detection recall.

This processor is designed to plug directly into streamlit-webrtc's
VideoProcessorBase interface:

    from streamlit_webrtc import webrtc_streamer, VideoProcessorFactory
    webrtc_streamer(video_processor_factory=VideoProcessorFactory(VideoProcessor))

Thread safety:
    streamlit-webrtc calls recv() from a background thread while the main
    Streamlit thread can update configuration.  We use a threading.Lock to
    guard shared state (known_students, attendance_marked).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

import av
import cv2
import numpy as np

try:
    from streamlit_webrtc import VideoProcessorBase
except ImportError:
    # Graceful degradation if streamlit-webrtc isn't installed
    class VideoProcessorBase:  # type: ignore[no-redef]
        pass

import config
from face_recognition_module.detector import detect_faces
from face_recognition_module.recognizer import recognize_faces, draw_recognition_results
from face_recognition_module.encodings_store import load_known_students
from database.db_operations import mark_attendance_if_new

logger = logging.getLogger(__name__)


class VideoProcessor(VideoProcessorBase):
    """
    Frame-by-frame face recognition processor.

    Attributes
    ----------
    threshold       : Recognition distance threshold (tunable from Streamlit UI)
    frame_skip      : Process only every Nth frame (config.FRAME_SKIP default)
    known_students  : Gallery loaded from MongoDB on initialisation
    attendance_log  : Dict of {student_id: timestamp} for confirmed attendance
    """

    def __init__(self) -> None:
        self._lock              = threading.Lock()
        self.threshold          = config.RECOGNITION_THRESHOLD
        self.frame_skip         = config.FRAME_SKIP
        self._frame_count       = 0
        self._last_results:     list[dict] = []
        self._last_annotated:   np.ndarray | None = None
        self.attendance_log:    dict[str, str] = {}   # student_id → "HH:MM:SS"

        # Load gallery once at init — reloaded on demand via reload_gallery()
        self._known_students: list[dict] = []
        self._load_gallery()

        logger.info("VideoProcessor initialised (frame_skip=%d).", self.frame_skip)

    # ── Public Interface ───────────────────────────────────────────────────────

    def reload_gallery(self) -> None:
        """Reload known students from MongoDB (call from Streamlit main thread)."""
        self._load_gallery()

    def get_attendance_log(self) -> dict[str, str]:
        with self._lock:
            return dict(self.attendance_log)

    def get_last_results(self) -> list[dict]:
        with self._lock:
            return list(self._last_results)

    # ── streamlit-webrtc interface ─────────────────────────────────────────────

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """
        Called by streamlit-webrtc for every incoming video frame.
        Processes every Nth frame to stay CPU-friendly.
        """
        img = frame.to_ndarray(format="bgr24")
        self._frame_count += 1

        if self._frame_count % self.frame_skip == 0:
            annotated = self._process_frame(img)
        else:
            # Re-use last annotated result on skipped frames
            with self._lock:
                annotated = self._last_annotated if self._last_annotated is not None else img

        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _load_gallery(self) -> None:
        students = load_known_students()
        with self._lock:
            self._known_students = students
        logger.info("Gallery refreshed: %d student(s).", len(students))

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        with self._lock:
            known_students = self._known_students
            threshold      = self.threshold

        detections = detect_faces(frame)
        results    = recognize_faces(detections, known_students, threshold=threshold)

        # Mark attendance asynchronously (don't block the video thread)
        for res in results:
            if res["student_id"] != "Unknown":
                self._mark_attendance_async(res)

        annotated = draw_recognition_results(frame, results)

        # Overlay live stats
        n_det = len(results)
        n_rec = sum(1 for r in results if r["student_id"] != "Unknown")
        cv2.putText(
            annotated,
            f"Detected: {n_det} | Recognised: {n_rec} | Unknown: {n_det - n_rec}",
            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2,
        )

        with self._lock:
            self._last_results   = results
            self._last_annotated = annotated

        return annotated

    def _mark_attendance_async(self, result: dict) -> None:
        """Fire-and-forget attendance marking (runs in the video thread)."""
        sid = result["student_id"]
        with self._lock:
            already_logged = sid in self.attendance_log

        if not already_logged:
            inserted = mark_attendance_if_new(
                student_id=sid,
                name=result["name"],
                matched_angle=result["matched_angle"],
                match_distance=result["distance"],
            )
            if inserted:
                ts = time.strftime("%H:%M:%S")
                with self._lock:
                    self.attendance_log[sid] = ts
                logger.info("Live attendance marked: %s at %s", sid, ts)
