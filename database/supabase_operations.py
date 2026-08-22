"""
database/supabase_operations.py
================================
All Supabase (PostgreSQL) read/write operations for EngageLens.

This module is a DROP-IN REPLACEMENT for db_operations.py.
Every public function has an identical signature and return type so that
switching the backend only requires changing one import line in each caller.

Mapping from MongoDB collections → Supabase tables:
  students          → public.students
  attendance        → public.attendance
  classes           → public.classes
  users             → public.users
  notifications_log → public.notifications_log
  audit_log         → public.audit_log

Design decisions:
  - face_encodings are stored as JSONB (same structure as MongoDB BSON arrays).
  - numpy arrays are serialised to plain Python lists on write and
    deserialised back to np.ndarray on read — identical to db_operations.py.
  - Attendance deduplication is enforced by a UNIQUE constraint on
    (student_id, date, session) in PostgreSQL — no extra Python check needed,
    but we keep the pre-check for a friendlier return value (True/False).
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import date, datetime
from typing import Any

import numpy as np

from .supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _serialise_encodings(angle_embeddings: list[dict]) -> list[dict]:
    """Convert numpy arrays → plain lists for JSON serialisation."""
    return [
        {
            "angle":      ae["angle"],
            "embedding":  ae["embedding"].tolist() if isinstance(ae["embedding"], np.ndarray) else ae["embedding"],
            "photo_path": ae.get("photo_path", ""),
        }
        for ae in angle_embeddings
    ]


def _deserialise_encodings(raw: list[dict]) -> list[dict]:
    """Convert plain lists → numpy arrays on read."""
    return [
        {
            "angle":      enc["angle"],
            "embedding":  np.array(enc["embedding"], dtype=np.float32),
            "photo_path": enc.get("photo_path", ""),
        }
        for enc in raw
    ]


# ── Student Operations ─────────────────────────────────────────────────────────

def insert_student(
    student_id: str,
    name: str,
    angle_embeddings: list[dict],
    roll_no: str = "",
    class_section: str = "",
    parent_telegram_chat_id: str | None = None,
) -> bool:
    """
    Insert a new student record into the 'students' table.
    Returns True on success, False if student_id already exists.
    """
    sb = get_supabase()

    # Idempotency check
    existing = sb.table("students").select("student_id").eq("student_id", student_id).execute()
    if existing.data:
        logger.warning("Student %s already enrolled — skipping insert.", student_id)
        return False

    doc = {
        "student_id":               student_id,
        "name":                     name,
        "roll_no":                  roll_no or student_id,
        "class_section":            class_section,
        "parent_telegram_chat_id":  parent_telegram_chat_id,
        "face_encodings":           _serialise_encodings(angle_embeddings),
        "enrolled_on":              datetime.utcnow().isoformat(),
    }

    sb.table("students").insert(doc).execute()
    logger.info(
        "Enrolled student %s (%s) | roll=%s | section=%s | angles=%d.",
        student_id, name, roll_no, class_section, len(angle_embeddings),
    )
    return True


def get_all_students() -> list[dict]:
    """
    Return all enrolled students with face_encodings as numpy arrays.
    """
    sb = get_supabase()
    rows = sb.table("students").select("*").execute().data or []
    students = []
    for row in rows:
        students.append({
            "student_id":              row["student_id"],
            "name":                    row["name"],
            "roll_no":                 row.get("roll_no") or row["student_id"],
            "class_section":           row.get("class_section", ""),
            "parent_telegram_chat_id": row.get("parent_telegram_chat_id"),
            "face_encodings":          _deserialise_encodings(row.get("face_encodings") or []),
            "enrolled_on":             row.get("enrolled_on"),
        })
    return students


def get_student_by_id(student_id: str) -> dict | None:
    """Return a single student document (embeddings as numpy arrays) or None."""
    sb = get_supabase()
    rows = sb.table("students").select("*").eq("student_id", student_id).execute().data
    if not rows:
        return None
    row = rows[0]
    return {
        "student_id":              row["student_id"],
        "name":                    row["name"],
        "roll_no":                 row.get("roll_no") or row["student_id"],
        "class_section":           row.get("class_section", ""),
        "parent_telegram_chat_id": row.get("parent_telegram_chat_id"),
        "face_encodings":          _deserialise_encodings(row.get("face_encodings") or []),
        "enrolled_on":             row.get("enrolled_on"),
    }


def delete_student(student_id: str) -> bool:
    """
    Remove a student. CASCADE deletes attendance + notification records.
    Returns True if the student existed and was deleted.
    """
    sb = get_supabase()
    result = sb.table("students").delete().eq("student_id", student_id).execute()
    deleted = bool(result.data)
    if deleted:
        logger.info("Deleted student %s (cascade removed attendance/notifications).", student_id)
    else:
        logger.warning("Attempted to delete non-existent student %s.", student_id)
    return deleted


def update_student_info(
    student_id: str,
    name: str,
    roll_no: str,
    class_section: str,
) -> tuple[bool, str]:
    """
    Update a student's editable profile fields.
    Returns (True, "") on success, (False, error_message) on failure.
    """
    sb = get_supabase()
    name          = name.strip()
    roll_no       = roll_no.strip()
    class_section = class_section.strip()

    if not name:
        return False, "Name cannot be empty."

    result = sb.table("students").update({
        "name":          name,
        "roll_no":       roll_no or student_id,
        "class_section": class_section,
    }).eq("student_id", student_id).execute()

    if not result.data:
        return False, f"Student '{student_id}' not found."

    # Propagate to attendance records (denormalised copies)
    sb.table("attendance").update({
        "name":          name,
        "roll_no":       roll_no or student_id,
        "class_section": class_section,
    }).eq("student_id", student_id).execute()

    logger.info(
        "Updated student %s → name=%s | roll=%s | section=%s",
        student_id, name, roll_no, class_section,
    )
    return True, ""


def update_student_encodings(student_id: str, angle_embeddings: list[dict]) -> bool:
    """
    Replace a student's face_encodings array (used when re-enrolling angles).
    Returns True if the student was found and updated.
    """
    sb = get_supabase()
    result = sb.table("students").update({
        "face_encodings": _serialise_encodings(angle_embeddings),
    }).eq("student_id", student_id).execute()
    return bool(result.data)


def update_student_chat_id(student_id: str, chat_id: str) -> bool:
    """
    Write a parent's Telegram chat_id to the student's record.
    Returns True if the student was found and updated.
    """
    sb = get_supabase()
    result = sb.table("students").update({
        "parent_telegram_chat_id": chat_id,
    }).eq("student_id", student_id).execute()
    if result.data:
        logger.info("Linked parent chat_id %s to student %s.", chat_id, student_id)
        return True
    logger.warning("update_student_chat_id: student %s not found.", student_id)
    return False


# ── Attendance Operations ──────────────────────────────────────────────────────

def mark_attendance_if_new(
    student_id: str,
    name: str,
    matched_angle: str,
    match_distance: float,
    session: str = "FN",
    roll_no: str = "",
    class_section: str = "",
) -> bool:
    """
    Insert an attendance record for today + session iff one doesn't already exist.
    Returns True if inserted (new), False if already marked.
    """
    sb = get_supabase()
    today = date.today().isoformat()

    # Pre-check (friendlier return value; DB UNIQUE constraint is the real guard)
    existing = (
        sb.table("attendance")
        .select("id")
        .eq("student_id", student_id)
        .eq("date", today)
        .eq("session", session)
        .execute()
    )
    if existing.data:
        return False

    doc: dict[str, Any] = {
        "student_id":     student_id,
        "name":           name,
        "roll_no":        roll_no or student_id,
        "class_section":  class_section,
        "date":           today,
        "session":        session,
        "timestamp":      datetime.utcnow().isoformat(),
        "status":         "Present",
        "matched_angle":  matched_angle,
        "match_distance": round(float(match_distance), 4),
    }
    sb.table("attendance").insert(doc).execute()
    logger.info(
        "Attendance marked for %s (%s) | session=%s | angle=%s | dist=%.4f",
        name, student_id, session, matched_angle, match_distance,
    )
    return True


def get_attendance_by_date(date_str: str, session: str | None = None) -> list[dict]:
    """
    Return all attendance records for a given date string ("YYYY-MM-DD").
    Optionally filter by session; None / "Both" returns both sessions.
    Sorted by name alphabetically.
    """
    sb = get_supabase()
    query = sb.table("attendance").select("*").eq("date", date_str)
    if session and session != "Both":
        query = query.eq("session", session)
    rows = query.order("name").execute().data or []

    for rec in rows:
        # Normalise timestamp to HH:MM:SS string
        ts = rec.get("timestamp")
        if ts and isinstance(ts, str) and "T" in ts:
            rec["timestamp"] = ts.split("T")[1][:8]
    return rows


def get_all_attendance() -> list[dict]:
    """Return every attendance record (for analytics / export)."""
    sb = get_supabase()
    rows = sb.table("attendance").select("*").order("timestamp", desc=True).execute().data or []
    for rec in rows:
        ts = rec.get("timestamp")
        if ts and isinstance(ts, str) and "T" in ts:
            rec["timestamp"] = ts.replace("T", " ")[:19]
    return rows


def get_present_student_ids(date_str: str, session: str) -> set[str]:
    """Return student_ids who have a Present record for the given date + session."""
    sb = get_supabase()
    rows = (
        sb.table("attendance")
        .select("student_id")
        .eq("date", date_str)
        .eq("session", session)
        .eq("status", "Present")
        .execute()
        .data or []
    )
    return {r["student_id"] for r in rows}


def get_all_enrolled_student_ids() -> set[str]:
    """Return the set of all enrolled student_ids."""
    sb = get_supabase()
    rows = sb.table("students").select("student_id").execute().data or []
    return {r["student_id"] for r in rows}


def get_absentees(date_str: str, session: str) -> list[dict]:
    """
    Compute absentees = all enrolled students − students present in (date, session).
    Returns list of student dicts (without face_encodings).
    """
    sb = get_supabase()
    present_ids = get_present_student_ids(date_str, session)
    rows = (
        sb.table("students")
        .select("student_id,name,roll_no,class_section,parent_telegram_chat_id")
        .execute()
        .data or []
    )
    absentees = [
        {
            "student_id":              r["student_id"],
            "name":                    r["name"],
            "roll_no":                 r.get("roll_no") or r["student_id"],
            "class_section":           r.get("class_section", ""),
            "parent_telegram_chat_id": r.get("parent_telegram_chat_id"),
        }
        for r in rows
        if r["student_id"] not in present_ids
    ]
    return sorted(absentees, key=lambda s: s["name"])


def get_attendance_stats() -> dict:
    """
    Return aggregate stats: total students, total attendance records,
    and per-date counts (for plotting).
    """
    sb = get_supabase()
    total_students = len(sb.table("students").select("student_id").execute().data or [])
    all_records    = sb.table("attendance").select("date").execute().data or []
    total_records  = len(all_records)

    by_date: dict[str, int] = {}
    for rec in all_records:
        d = rec.get("date", "")
        if d:
            by_date[d] = by_date.get(d, 0) + 1

    return {
        "total_students": total_students,
        "total_records":  total_records,
        "by_date":        dict(sorted(by_date.items())),
    }


# ── Class Operations ───────────────────────────────────────────────────────────

def get_all_classes() -> list[dict]:
    """Return all class documents sorted by name."""
    sb = get_supabase()
    return sb.table("classes").select("class_id,name,created_by,created_on").order("name").execute().data or []


def get_class_sections() -> list[str]:
    """
    Return a sorted list of class section name strings for dropdowns.
    Falls back to deriving from student records if classes table is empty.
    """
    sb = get_supabase()
    rows = sb.table("classes").select("name").order("name").execute().data or []
    if rows:
        return [r["name"] for r in rows]
    # Fallback: derive from existing student records
    student_rows = sb.table("students").select("class_section").execute().data or []
    return sorted({r["class_section"] for r in student_rows if r.get("class_section")})


def create_class(name: str, created_by: str = "system") -> tuple[bool, str]:
    """
    Create a new class.
    Returns (True, class_id) on success, (False, error_msg) on failure.
    """
    sb = get_supabase()
    name = name.strip()
    if not name:
        return False, "Class name cannot be empty."

    existing = sb.table("classes").select("class_id").eq("name", name).execute().data
    if existing:
        return False, f"Class '{name}' already exists."

    class_id = f"CLS-{_uuid.uuid4().hex[:8].upper()}"
    sb.table("classes").insert({
        "class_id":   class_id,
        "name":       name,
        "created_by": created_by,
        "created_on": datetime.utcnow().isoformat(),
    }).execute()
    logger.info("Created class '%s' (id=%s) by %s.", name, class_id, created_by)
    return True, class_id


def delete_class(class_id: str, actor: str = "system") -> tuple[bool, str]:
    """
    Delete a class by class_id. Refuses if students are still assigned to it.
    Returns (True, "") or (False, error_msg).
    """
    sb = get_supabase()
    cls_rows = sb.table("classes").select("*").eq("class_id", class_id).execute().data
    if not cls_rows:
        return False, "Class not found."
    cls = cls_rows[0]

    # Safety: block if students exist in this class
    students = sb.table("students").select("student_id").eq("class_section", cls["name"]).execute().data or []
    if students:
        return False, (
            f"Cannot delete — {len(students)} student(s) are still assigned to "
            f"'{cls['name']}'. Reassign them first."
        )

    sb.table("classes").delete().eq("class_id", class_id).execute()
    logger.info("Deleted class '%s' by %s.", cls["name"], actor)
    return True, ""


# ── Notification Log Operations ────────────────────────────────────────────────

def log_notification(
    student_id: str,
    date_str: str,
    session: str,
    status: str,
    telegram_message_id: int | None = None,
) -> None:
    """
    Upsert a notifications_log row for (student_id, date, session).
    status values: "sent" | "failed" | "skipped_no_chat_id"
    """
    sb = get_supabase()
    doc: dict[str, Any] = {
        "student_id": student_id,
        "date":       date_str,
        "session":    session,
        "sent_at":    datetime.utcnow().isoformat(),
        "status":     status,
    }
    if telegram_message_id is not None:
        doc["telegram_message_id"] = telegram_message_id

    sb.table("notifications_log").upsert(
        doc,
        on_conflict="student_id,date,session",
    ).execute()
    logger.info(
        "Notification log: student=%s | date=%s | session=%s | status=%s",
        student_id, date_str, session, status,
    )


def get_notification_log(
    student_id: str,
    date_str: str,
    session: str,
) -> dict | None:
    """
    Return the notifications_log row for (student_id, date, session), or None.
    """
    sb = get_supabase()
    rows = (
        sb.table("notifications_log")
        .select("*")
        .eq("student_id", student_id)
        .eq("date", date_str)
        .eq("session", session)
        .execute()
        .data
    )
    return rows[0] if rows else None
