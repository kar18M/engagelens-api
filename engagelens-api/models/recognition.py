# Pydantic models for recognition / enroll endpoints
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class RecognitionResult(BaseModel):
    student_id: str
    name: str
    matched_angle: str
    distance: float
    det_score: float
    bbox: list[int]  # [x1, y1, x2, y2]


class RecognizeResponse(BaseModel):
    results: list[RecognitionResult]
    total_detected: int
    total_recognised: int


class EnrollRequest(BaseModel):
    student_id: str
    name: str
    roll_no: str = ""
    class_section: str = ""
    # angle → base64 image pairs are sent as multipart form, not JSON


class EnrollResponse(BaseModel):
    success: bool
    message: str
    angles_enrolled: list[str] = []
    errors: list[str] = []
