"""
database/db_operations.py
===========================
All MongoDB read/write operations for EngageLens.

Design decisions:
  - Embeddings are stored as plain Python lists (JSON-serialisable) and
    converted back to numpy arrays on read.
  - Attendance deduplication is enforced in Python (check before insert),
    with a backing compound index as a safety net (see mongo_client.py).

Phase 9 changes:
  - students: added roll_no, class_section, parent_telegram_chat_id fields.
  - attendance: added session field; compound key is now (student_id, date, session).
  - New collection: notifications_log — one doc per (student_id, date, session) alert.
  - New functions: get_absentees, get_present_student_ids, get_all_enrolled_student_ids,
    log_notification, get_notification_log, update_student_chat_id.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import numpy as np

from .mongo_client import get_db

logger = logging.getLogger(__name__)


# ── Student Operations ─────────────────────────────────────────────────────────

def insert_student(
    student_id: str,
    name: str,
    angle_embeddings: list[dict],  # [{"angle": str, "embedding": np.ndarray, "photo_path": str}]
    roll_no: str = "",
    class_section: str = "",
    parent_telegram_chat_id: str | None = None,
) -> bool:
    """
    Insert a new student record into the 'students' collection.

    Parameters
    ----------
    student_id              : Unique identifier, e.g. "CS101"
    name                    : Human-readable name
    angle_embeddings        : List of dicts, each with keys:
                                angle      — one of config.VALID_ANGLES
                                embedding  — numpy array of shape (512,)
                                photo_path — relative path to stored photo
    roll_no                 : Roll number for message formatting, e.g. "21CS045"
    class_section           : Class/section string, e.g. "CSE-A"
    parent_telegram_chat_id : Parent's Telegram chat ID (populated by linker bot)

    Returns
    -------
    True on success, False if student_id already exists.
    """
    db = get_db()
    collection = db["students"]

    if collection.find_one({"student_id": student_id}):
        logger.warning("Student %s already enrolled — skipping insert.", student_id)
        return False

    # Convert numpy arrays → plain lists for BSON serialisation
    serialised_encodings = [
        {
            "angle":      ae["angle"],
            "embedding":  ae["embedding"].tolist() if isinstance(ae["embedding"], np.ndarray) else ae["embedding"],
            "photo_path": ae["photo_path"],
        }
        for ae in angle_embeddings
    ]

    doc = {
        "student_id":               student_id,
        "name":                     name,
        "roll_no":                  roll_no or student_id,   # fallback to student_id if blank
        "class_section":            class_section,
        "parent_telegram_chat_id":  parent_telegram_chat_id,
        "face_encodings":           serialised_encodings,
        "enrolled_on":              datetime.utcnow(),
    }

    collection.insert_one(doc)
    logger.info(
        "Enrolled student %s (%s) | roll=%s | section=%s | angles=%d.",
        student_id, name, roll_no, class_section, len(angle_embeddings),
    )
    return True


def get_all_students() -> list[dict]:
    """
    Return all enrolled students with embeddings converted back to numpy arrays.

    Return structure per student:
    {
        "student_id":               str,
        "name":                     str,
        "roll_no":                  str,
        "class_section":            str,
        "parent_telegram_chat_id":  str | None,
        "face_encodings":           [{"angle": str, "embedding": np.ndarray, "photo_path": str}, ...],
        "enrolled_on":              datetime,
    }
    """
    db = get_db()
    students = []

    for doc in db["students"].find({}, {"_id": 0}):
        face_encodings = [
            {
                "angle":      enc["angle"],
                "embedding":  np.array(enc["embedding"], dtype=np.float32),
                "photo_path": enc.get("photo_path", ""),
            }
            for enc in doc.get("face_encodings", [])
        ]
        students.append({
            "student_id":              doc["student_id"],
            "name":                    doc["name"],
            "roll_no":                 doc.get("roll_no", doc["student_id"]),
            "class_section":           doc.get("class_section", ""),
            "parent_telegram_chat_id": doc.get("parent_telegram_chat_id"),
            "face_encodings":          face_encodings,
            "enrolled_on":             doc.get("enrolled_on"),
        })

    return students


def get_student_by_id(student_id: str) -> dict | None:
    """Return a single student document (embeddings as numpy arrays) or None."""
    db = get_db()
    doc = db["students"].find_one({"student_id": student_id}, {"_id": 0})
    if doc is None:
        return None

    doc["face_encodings"] = [
        {
            "angle":      enc["angle"],
            "embedding":  np.array(enc["embedding"], dtype=np.float32),
            "photo_path": enc.get("photo_path", ""),
        }
        for enc in doc.get("face_encodings", [])
    ]
    doc.setdefault("roll_no", doc["student_id"])
    doc.setdefault("class_section", "")
    doc.setdefault("parent_telegram_chat_id", None)
    return doc


def delete_student(student_id: str) -> bool:
    """
    Remove a student and all their attendance + notification records.
    Returns True if the student existed and was deleted.
    """
    db = get_db()
    result = db["students"].delete_one({"student_id": student_id})
    if result.deleted_count:
        db["attendance"].delete_many({"student_id": student_id})
        db["notifications_log"].delete_many({"student_id": student_id})
        logger.info("Deleted student %s and their attendance/notification records.", student_id)
        return True
    logger.warning("Attempted to delete non-existent student %s.", student_id)
    return False


def update_student_info(
    student_id: str,
    name: str,
    roll_no: str,
    class_section: str,
) -> tuple[bool, str]:
    """
    Update a student's editable profile fields (name, roll_no, class_section).
    Also propagates changes to existing attendance records so denormalised
    fields stay consistent.

    Returns (True, "") on success, (False, error_message) on failure.
    """
    db = get_db()

    name          = name.strip()
    roll_no       = roll_no.strip()
    class_section = class_section.strip()

    if not name:
        return False, "Name cannot be empty."

    result = db["students"].update_one(
        {"student_id": student_id},
        {"$set": {
            "name":          name,
            "roll_no":       roll_no or student_id,
            "class_section": class_section,
        }},
    )
    if result.matched_count == 0:
        return False, f"Student '{student_id}' not found."

    # Propagate to attendance records (denormalised copies)
    db["attendance"].update_many(
        {"student_id": student_id},
        {"$set": {
            "name":          name,
            "roll_no":       roll_no or student_id,
            "class_section": class_section,
        }},
    )

    logger.info(
        "Updated student %s → name=%s | roll=%s | section=%s",
        student_id, name, roll_no, class_section,
    )
    return True, ""



def update_student_encodings(student_id: str, angle_embeddings: list[dict]) -> bool:
    """
    Replace a student's face_encodings array (used when re-enrolling angles).
    Returns True if the document was found and updated.
    """
    db = get_db()
    serialised = [
        {
            "angle":      ae["angle"],
            "embedding":  ae["embedding"].tolist() if isinstance(ae["embedding"], np.ndarray) else ae["embedding"],
            "photo_path": ae["photo_path"],
        }
        for ae in angle_embeddings
    ]
    result = db["students"].update_one(
        {"student_id": student_id},
        {"$set": {"face_encodings": serialised}},
    )
    return result.matched_count > 0


def update_student_chat_id(student_id: str, chat_id: str) -> bool:
    """
    Write a parent's Telegram chat_id to the student's record.
    Called by the linker polling thread when a parent sends /start {student_id}.
    Returns True if the student was found and updated.
    """
    db = get_db()
    result = db["students"].update_one(
        {"student_id": student_id},
        {"$set": {"parent_telegram_chat_id": chat_id}},
    )
    if result.matched_count:
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

    Parameters
    ----------
    student_id    : The recognised student's ID
    name          : Student name (denormalised for easy querying)
    matched_angle : Which stored angle embedding produced the best match
    match_distance: Cosine distance of the best match (lower = better)
    session       : "FN" (Forenoon) or "AN" (Afternoon) — part of the unique key
    roll_no       : Denormalised for display without joins
    class_section : Denormalised for display without joins

    Returns
    -------
    True  — record inserted (first attendance event for this student/date/session)
    False — student was already marked present for this session today
    """
    db = get_db()
    today = date.today().isoformat()   # "YYYY-MM-DD"

    existing = db["attendance"].find_one(
        {"student_id": student_id, "date": today, "session": session}
    )
    if existing:
        return False

    doc: dict[str, Any] = {
        "student_id":     student_id,
        "name":           name,
        "roll_no":        roll_no or student_id,
        "class_section":  class_section,
        "date":           today,
        "session":        session,
        "timestamp":      datetime.utcnow(),
        "status":         "Present",
        "matched_angle":  matched_angle,
        "match_distance": round(float(match_distance), 4),
    }
    db["attendance"].insert_one(doc)
    logger.info(
        "Attendance marked for %s (%s) | session=%s | angle=%s | dist=%.4f",
        name, student_id, session, matched_angle, match_distance,
    )
    return True


def get_attendance_by_date(date_str: str, session: str | None = None) -> list[dict]:
    """
    Return all attendance records for a given date string ("YYYY-MM-DD").
    Optionally filter by session ("FN" or "AN"); None returns both.
    Sorted by name alphabetically.
    """
    db = get_db()
    query: dict[str, Any] = {"date": date_str}
    if session and session != "Both":
        query["session"] = session

    records = list(
        db["attendance"].find(query, {"_id": 0}).sort("name", 1)
    )
    # Convert datetime objects to ISO strings for clean display
    for rec in records:
        if isinstance(rec.get("timestamp"), datetime):
            rec["timestamp"] = rec["timestamp"].strftime("%H:%M:%S")
    return records


def get_all_attendance() -> list[dict]:
    """Return every attendance record (for analytics / export)."""
    db = get_db()
    records = list(db["attendance"].find({}, {"_id": 0}).sort("timestamp", -1))
    for rec in records:
        if isinstance(rec.get("timestamp"), datetime):
            rec["timestamp"] = rec["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    return records


def get_present_student_ids(date_str: str, session: str) -> set[str]:
    """
    Return a set of student_ids who have a Present record for the given
    date + session combination. Used by absentee computation.
    """
    db = get_db()
    docs = db["attendance"].find(
        {"date": date_str, "session": session, "status": "Present"},
        {"student_id": 1, "_id": 0},
    )
    return {d["student_id"] for d in docs}


def get_all_enrolled_student_ids() -> set[str]:
    """Return the set of all enrolled student_ids."""
    db = get_db()
    docs = db["students"].find({}, {"student_id": 1, "_id": 0})
    return {d["student_id"] for d in docs}


def get_absentees(date_str: str, session: str) -> list[dict]:
    """
    Compute absentees = all enrolled students − students present in (date, session).

    Returns a list of full student documents (from 'students' collection) for
    students who are NOT marked present in the given session. Documents include
    roll_no, class_section, parent_telegram_chat_id for the alert UI.

    Note: This is a per-session diff. A student absent in FN but present in AN
    appears only in FN absentees and vice versa — the two sessions are fully
    independent records.
    """
    db = get_db()
    present_ids = get_present_student_ids(date_str, session)

    # Fetch all enrolled students not in the present set
    absentees = []
    for doc in db["students"].find({}, {"_id": 0, "face_encodings": 0}):
        if doc["student_id"] not in present_ids:
            absentees.append({
                "student_id":              doc["student_id"],
                "name":                    doc["name"],
                "roll_no":                 doc.get("roll_no", doc["student_id"]),
                "class_section":           doc.get("class_section", ""),
                "parent_telegram_chat_id": doc.get("parent_telegram_chat_id"),
            })

    return sorted(absentees, key=lambda s: s["name"])


def get_attendance_stats() -> dict:
    """
    Return aggregate stats: total students enrolled, total attendance records,
    and per-date counts (for plotting).
    """
    db = get_db()
    total_students = db["students"].count_documents({})
    total_records  = db["attendance"].count_documents({})

    pipeline = [
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    by_date = {doc["_id"]: doc["count"] for doc in db["attendance"].aggregate(pipeline)}

    return {
        "total_students": total_students,
        "total_records":  total_records,
        "by_date":        by_date,
    }


# ── Class Operations ───────────────────────────────────────────────────────────

def get_all_classes() -> list[dict]:
    """
    Return all class documents from the 'classes' collection.
    Each doc: { class_id, name, created_by, created_on }
    """
    db = get_db()
    return list(db["classes"].find({}, {"_id": 0}).sort("name", 1))


def get_class_sections() -> list[str]:
    """
    Return a sorted list of class section name strings.
    Used to populate dropdowns across the app.
    Falls back to deriving from student records if classes collection is empty.
    """
    db = get_db()
    classes = list(db["classes"].find({}, {"_id": 0, "name": 1}).sort("name", 1))
    if classes:
        return [c["name"] for c in classes]
    # Fallback: derive from existing student records
    return sorted(set(
        s.get("class_section", "")
        for s in db["students"].find({}, {"_id": 0, "class_section": 1})
        if s.get("class_section")
    ))


def create_class(name: str, created_by: str = "system") -> tuple[bool, str]:
    """
    Create a new class in the 'classes' collection.
    Returns (True, class_id) on success, (False, error_msg) on failure.
    """
    import uuid as _uuid
    db = get_db()
    name = name.strip()
    if not name:
        return False, "Class name cannot be empty."
    if db["classes"].find_one({"name": name}):
        return False, f"Class '{name}' already exists."
    class_id = f"CLS-{_uuid.uuid4().hex[:8].upper()}"
    doc = {
        "class_id":   class_id,
        "name":       name,
        "created_by": created_by,
        "created_on": datetime.utcnow(),
    }
    db["classes"].insert_one(doc)
    logger.info("Created class '%s' (id=%s) by %s.", name, class_id, created_by)
    return True, class_id


def delete_class(class_id: str, actor: str = "system") -> tuple[bool, str]:
    """
    Delete a class by class_id. Refuses if students are still assigned to it.
    Returns (True, "") or (False, error_msg).
    """
    db = get_db()
    cls = db["classes"].find_one({"class_id": class_id}, {"_id": 0})
    if not cls:
        return False, "Class not found."
    # Safety: block if students exist in this class
    count = db["students"].count_documents({"class_section": cls["name"]})
    if count > 0:
        return False, f"Cannot delete — {count} student(s) are still assigned to '{cls['name']}'. Reassign them first."
    db["classes"].delete_one({"class_id": class_id})
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
    Upsert a notifications_log document for (student_id, date, session).
    Called by send_batch_alerts() after each send attempt.

    status values: "sent" | "failed" | "skipped_no_chat_id"
    """
    db = get_db()
    doc: dict[str, Any] = {
        "student_id": student_id,
        "date":       date_str,
        "session":    session,
        "sent_at":    datetime.utcnow(),
        "status":     status,
    }
    if telegram_message_id is not None:
        doc["telegram_message_id"] = telegram_message_id

    db["notifications_log"].update_one(
        {"student_id": student_id, "date": date_str, "session": session},
        {"$set": doc},
        upsert=True,
    )
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
    Return the notifications_log document for (student_id, date, session),
    or None if no attempt has been made yet.
    """
    db = get_db()
    return db["notifications_log"].find_one(
        {"student_id": student_id, "date": date_str, "session": session},
        {"_id": 0},
    )
