"""
database/__init__.py
=====================
Exposes all database operations at the package level.

Backend selection is controlled by the DB_BACKEND environment variable:
  DB_BACKEND=supabase  → use Supabase (PostgreSQL) cloud database
  DB_BACKEND=mongo     → use local MongoDB (default, original behaviour)

Set DB_BACKEND=supabase in your .env file to switch to the cloud database.
"""

import os

_backend = os.environ.get("DB_BACKEND", "mongo").strip().lower()

if _backend == "supabase":
    from .supabase_client import get_supabase as _get_backend, SupabaseConnectionError as ConnectionError
    from .supabase_operations import (
        insert_student,
        get_all_students,
        get_student_by_id,
        delete_student,
        update_student_info,
        update_student_encodings,
        update_student_chat_id,
        mark_attendance_if_new,
        get_attendance_by_date,
        get_all_attendance,
        get_present_student_ids,
        get_all_enrolled_student_ids,
        get_absentees,
        get_attendance_stats,
        get_all_classes,
        get_class_sections,
        create_class,
        delete_class,
        log_notification,
        get_notification_log,
    )
    # Alias so existing code that calls get_db() still works
    def get_db():
        return _get_backend()
    MongoConnectionError = ConnectionError
else:
    # Default: original MongoDB backend
    from .mongo_client import get_db, MongoConnectionError
    from .db_operations import (
        insert_student,
        get_all_students,
        get_student_by_id,
        delete_student,
        update_student_info,
        update_student_encodings,
        update_student_chat_id,
        mark_attendance_if_new,
        get_attendance_by_date,
        get_all_attendance,
        get_present_student_ids,
        get_all_enrolled_student_ids,
        get_absentees,
        get_attendance_stats,
        get_all_classes,
        get_class_sections,
        create_class,
        delete_class,
        log_notification,
        get_notification_log,
    )

__all__ = [
    "get_db",
    "MongoConnectionError",
    "insert_student",
    "get_all_students",
    "get_student_by_id",
    "delete_student",
    "update_student_info",
    "update_student_encodings",
    "update_student_chat_id",
    "mark_attendance_if_new",
    "get_attendance_by_date",
    "get_all_attendance",
    "get_present_student_ids",
    "get_all_enrolled_student_ids",
    "get_absentees",
    "get_attendance_stats",
    "get_all_classes",
    "get_class_sections",
    "create_class",
    "delete_class",
    "log_notification",
    "get_notification_log",
]

