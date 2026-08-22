"""
routers/attendance.py
======================
Attendance log, stats, absentees, and manual mark endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from database.db_operations import (
    mark_attendance_if_new,
    get_attendance_by_date,
    get_all_attendance,
    get_attendance_stats,
    get_absentees,
)
from dependencies import get_current_user, require_role, TokenData
from models.attendance import (
    AttendanceMarkRequest,
    AttendanceRecord,
    AttendanceStatsResponse,
    AbsenteeResponse,
)

router = APIRouter()


@router.post("/mark")
async def mark_attendance(
    body: AttendanceMarkRequest,
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """Mark a student present for the given session. Idempotent — safe to call twice."""
    inserted = mark_attendance_if_new(
        student_id=body.student_id,
        name=body.name,
        matched_angle=body.matched_angle,
        match_distance=body.match_distance,
        session=body.session,
        roll_no=body.roll_no,
        class_section=body.class_section,
    )
    return {
        "inserted": inserted,
        "message": "Marked present." if inserted else "Already marked present for this session.",
    }


@router.get("/", response_model=list[AttendanceRecord])
async def get_attendance(
    date_str: Optional[str] = None,
    session: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
):
    """Return attendance records. Defaults to today if no date given."""
    if not date_str:
        date_str = date.today().isoformat()
    records = get_attendance_by_date(date_str, session)
    return [AttendanceRecord(**r) for r in records]


@router.get("/all", response_model=list[AttendanceRecord])
async def get_all(current_user: TokenData = Depends(require_role("teacher", "admin"))):
    """Return every attendance record (for export / analytics)."""
    records = get_all_attendance()
    return [AttendanceRecord(**r) for r in records]


@router.get("/stats", response_model=AttendanceStatsResponse)
async def attendance_stats(current_user: TokenData = Depends(require_role("teacher", "admin"))):
    """Return aggregate statistics: totals and per-date counts."""
    stats = get_attendance_stats()
    return AttendanceStatsResponse(**stats)


@router.get("/absentees", response_model=list[AbsenteeResponse])
async def absentees(
    date_str: Optional[str] = None,
    session: str = "FN",
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """Return students absent for the given date+session. Defaults to today."""
    if not date_str:
        date_str = date.today().isoformat()
    result = get_absentees(date_str, session)
    return [AbsenteeResponse(**s) for s in result]


@router.get("/student/{student_id}", response_model=list[AttendanceRecord])
async def student_attendance_history(
    student_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Return all attendance records for a specific student.
    Students can only see their own records.
    """
    # Students can only see their own history
    if current_user.role == "student" and current_user.linked_student_id != student_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=403, detail="You can only view your own attendance history.")

    all_records = get_all_attendance()
    student_records = [r for r in all_records if r.get("student_id") == student_id]
    return [AttendanceRecord(**r) for r in student_records]
