"""
database/mongo_client.py
=========================
Central MongoDB connection factory.

Usage:
    from database.mongo_client import get_db

If MongoDB is not running this raises MongoConnectionError with a human-friendly
message that Streamlit pages can catch and display instead of crashing.

Phase 9: Updated compound index on attendance to (student_id, date, session)
and added notifications_log index.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

import config

logger = logging.getLogger(__name__)


class MongoConnectionError(RuntimeError):
    """Raised when EngageLens cannot reach the local MongoDB instance."""


@lru_cache(maxsize=1)
def _get_client() -> MongoClient:
    """
    Return a cached MongoClient.  lru_cache ensures we create only one
    connection pool for the lifetime of the Python process, which is what
    we want because Streamlit reruns the script on every interaction.
    """
    try:
        client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=3_000,   # fail fast on localhost
        )
        # Force a real connection attempt so we detect failures here, not later.
        client.admin.command("ping")
        logger.info("MongoDB connected at %s", config.MONGO_URI)
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        raise MongoConnectionError(
            f"Cannot reach MongoDB at {config.MONGO_URI}. "
            "Please start MongoDB with:  sudo systemctl start mongod  "
            "(or  mongod --dbpath /data/db  if installed manually)."
        ) from exc


def get_db() -> pymongo.database.Database:
    """
    Return the 'engagelens' database object.
    Raises MongoConnectionError if the server is not reachable.
    """
    client = _get_client()
    db = client[config.DB_NAME]
    _ensure_indexes(db)
    return db


def _ensure_indexes(db: pymongo.database.Database) -> None:
    """
    Idempotently create all required indexes.
    Called every time get_db() is invoked — pymongo is smart enough not to
    recreate an index that already exists.

    Phase 9 migration note:
    The old index 'attendance_student_date_idx' covered (student_id, date).
    It is dropped here and replaced with (student_id, date, session) so the
    deduplication logic in mark_attendance_if_new works per-session.
    Existing attendance documents without a 'session' field are unaffected
    functionally — they simply won't match FN/AN session filters.
    """
    # ── Drop legacy index if it still exists (idempotent) ─────────────────────
    try:
        db["attendance"].drop_index("attendance_student_date_idx")
        logger.info("Dropped legacy attendance_student_date_idx index.")
    except Exception:
        pass  # Index didn't exist — that's fine

    # ── Phase 9: compound index on (student_id, date, session) ────────────────
    # Not unique=True because Python-level dedup in mark_attendance_if_new is
    # the primary guard; this index is for query performance + safety net.
    db["attendance"].create_index(
        [
            ("student_id", pymongo.ASCENDING),
            ("date",       pymongo.ASCENDING),
            ("session",    pymongo.ASCENDING),
        ],
        name="attendance_student_date_session_idx",
    )

    # ── Fast lookup of students by student_id ─────────────────────────────────
    db["students"].create_index(
        [("student_id", pymongo.ASCENDING)],
        unique=True,
        name="students_student_id_unique",
    )

    # ── notifications_log: one document per (student_id, date, session) ───────
    db["notifications_log"].create_index(
        [
            ("student_id", pymongo.ASCENDING),
            ("date",       pymongo.ASCENDING),
            ("session",    pymongo.ASCENDING),
        ],
        name="notif_log_student_date_session_idx",
    )

    # ── Phase 10: users — unique username ──────────────────────────────────────
    db["users"].create_index(
        [("username", pymongo.ASCENDING)],
        unique=True,
        name="users_username_unique",
    )
    db["users"].create_index(
        [("user_id", pymongo.ASCENDING)],
        unique=True,
        name="users_user_id_unique",
    )

    # ── Phase 10: audit_log — searchable by actor + timestamp ─────────────────
    db["audit_log"].create_index(
        [
            ("actor_user_id", pymongo.ASCENDING),
            ("timestamp",     pymongo.DESCENDING),
        ],
        name="audit_log_actor_ts_idx",
    )
    db["audit_log"].create_index(
        [("action", pymongo.ASCENDING)],
        name="audit_log_action_idx",
    )
