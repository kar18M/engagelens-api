# Pydantic models for attendance endpoints
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AttendanceMarkRequest(BaseModel):
    student_id: str
    name: str
    matched_angle: str = "front"
    match_distance: float = 0.0
    session: str = "FN"
    roll_no: str = ""
    class_section: str = ""


class AttendanceRecord(BaseModel):
    student_id: str
    name: str
    roll_no: str = ""
    class_section: str = ""
    date: str
    session: str
    timestamp: str = ""
    status: str = "Present"
    matched_angle: str = ""
    match_distance: float = 0.0


class AttendanceStatsResponse(BaseModel):
    total_students: int
    total_records: int
    by_date: dict


class AbsenteeResponse(BaseModel):
    student_id: str
    name: str
    roll_no: str = ""
    class_section: str = ""
    parent_telegram_chat_id: Optional[str] = None
