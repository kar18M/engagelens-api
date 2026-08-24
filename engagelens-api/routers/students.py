from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import from the abstraction layer (database/__init__.py) which selects
# the correct backend (Supabase or MongoDB) via DB_BACKEND env var.
# Do NOT import from database.db_operations directly — it imports pymongo at top level.
from database import (
    get_all_students,
    get_student_by_id,
    delete_student,
    update_student_info,
)
from dependencies import get_current_user, require_role, TokenData
from models.student import StudentResponse, StudentUpdate

router = APIRouter()


def _to_response(doc: dict) -> StudentResponse:
    """Convert a raw student DB document to the API response model."""
    enrolled_on = doc.get("enrolled_on")
    angles = [enc["angle"] for enc in doc.get("face_encodings", [])]
    return StudentResponse(
        student_id=doc["student_id"],
        name=doc["name"],
        roll_no=doc.get("roll_no", ""),
        class_section=doc.get("class_section", ""),
        parent_telegram_chat_id=doc.get("parent_telegram_chat_id"),
        enrolled_on=str(enrolled_on) if enrolled_on else None,
        angles_enrolled=angles,
    )


@router.get("/", response_model=list[StudentResponse])
async def list_students(current_user: TokenData = Depends(get_current_user)):
    """Return all enrolled students (without face embeddings — they're large)."""
    students = get_all_students()
    return [_to_response(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Return a single student by ID."""
    student = get_student_by_id(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
    return _to_response(student)


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    body: StudentUpdate,
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """Update a student's profile info (name, roll_no, class_section)."""
    ok, msg = update_student_info(student_id, body.name, body.roll_no, body.class_section)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    student = get_student_by_id(student_id)
    return _to_response(student)


@router.delete("/{student_id}")
async def remove_student(
    student_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Delete a student and all their attendance records. Admin only."""
    ok = delete_student(student_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
    return {"message": f"Student '{student_id}' deleted successfully."}
