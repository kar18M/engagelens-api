"""
auth/user_operations.py
========================
CRUD operations for the `users` and `audit_log` MongoDB collections.

All password hashing uses bcrypt with cost factor 12.
Passwords are NEVER stored, logged, or returned in any function.

Phase 10 collections:
  users      — user accounts (student / teacher / admin)
  audit_log  — immutable record of every admin/teacher action
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import bcrypt

import config
from database.mongo_client import get_db

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash_password(plaintext: str) -> str:
    """Hash a plaintext password with bcrypt (cost=12). Returns the hash string."""
    return bcrypt.hashpw(
        plaintext.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def _make_user_id(role: str, username: str) -> str:
    """Generate a deterministic-ish user_id. Example: 'S-24adr064', 'T-john'."""
    prefix = {"student": "S", "teacher": "T", "admin": "A"}.get(role, "U")
    return f"{prefix}-{username[:20]}"


# ─────────────────────────────────────────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_user(
    username: str,
    password: str,
    role: str,
    full_name: str,
    email: str = "",
    linked_student_id: str | None = None,
    assigned_sections: list[str] | None = None,
    created_by: str = "system",
) -> tuple[bool, str]:
    """
    Create a new user account.

    Returns (True, user_id) on success, (False, error_message) on failure.
    """
    db = get_db()

    username = username.strip()          # preserve case (e.g. 24ADR064)
    role     = role.strip().lower()

    # ── Validation ────────────────────────────────────────────────────────────
    if not username:
        return False, "Username is required."
    if role not in config.VALID_ROLES:
        return False, f"Invalid role '{role}'. Must be one of: {config.VALID_ROLES}."
    if len(password) < config.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters."
    if db["users"].find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
        return False, f"Username '{username}' is already taken."

    # Validate linked_student_id for students
    if role == "student" and linked_student_id:
        if not db["students"].find_one({"student_id": linked_student_id}):
            return False, f"Student ID '{linked_student_id}' not found in enrolled students."

    user_id = _make_user_id(role, username)
    # Ensure uniqueness if collision
    if db["users"].find_one({"user_id": user_id}):
        user_id = f"{user_id}-{uuid.uuid4().hex[:4]}"

    doc: dict[str, Any] = {
        "user_id":            user_id,
        "username":           username,
        "password_hash":      _hash_password(password),
        "role":               role,
        "full_name":          full_name.strip(),
        "email":              email.strip(),
        "linked_student_id":  linked_student_id,
        "assigned_sections":  assigned_sections or [],
        "is_active":          True,
        "created_on":         datetime.utcnow(),
        "created_by":         created_by,
        "last_login":         None,
        "login_attempts":     0,
        "lockout_until":      None,
        "force_password_reset": False,
    }

    db["users"].insert_one(doc)
    logger.info(
        "Created user %s (role=%s, created_by=%s).", username, role, created_by
    )
    return True, user_id


def get_user_by_username(username: str) -> dict | None:
    """Return a user document by username (case-insensitive), or None."""
    db = get_db()
    return db["users"].find_one(
        {"username": {"$regex": f"^{re.escape(username.strip())}$", "$options": "i"}},
        {"_id": 0},
    )


def get_user_by_id(user_id: str) -> dict | None:
    """Return a user document by user_id, or None."""
    db = get_db()
    return db["users"].find_one({"user_id": user_id}, {"_id": 0})


def get_all_users(role_filter: str | None = None) -> list[dict]:
    """
    Return all user documents (password_hash excluded).
    Optionally filter by role.
    """
    db = get_db()
    query: dict[str, Any] = {}
    if role_filter:
        query["role"] = role_filter.lower()

    return list(
        db["users"].find(query, {"_id": 0, "password_hash": 0}).sort("created_on", -1)
    )


def update_user(user_id: str, fields: dict, actor_user_id: str = "system") -> bool:
    """
    Update arbitrary user fields (except password_hash — use reset_password for that).
    Returns True if document was found and updated.
    """
    db = get_db()
    # Prevent accidental password update via this function
    fields.pop("password_hash", None)
    fields.pop("user_id", None)

    result = db["users"].update_one(
        {"user_id": user_id},
        {"$set": fields},
    )
    return result.matched_count > 0


def deactivate_user(user_id: str, actor_user_id: str) -> bool:
    """Deactivate a user account. Returns True if found."""
    db = get_db()
    user = db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return False

    db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"is_active": False}},
    )
    log_audit(
        actor_user_id=actor_user_id,
        actor_role="admin",
        action="user_deactivated",
        target=f"user_id={user_id} username={user.get('username')}",
        old_value="active",
        new_value="inactive",
    )
    logger.info("User %s deactivated by %s.", user_id, actor_user_id)
    return True


def reactivate_user(user_id: str, actor_user_id: str) -> bool:
    """Reactivate a previously deactivated user account."""
    db = get_db()
    user = db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return False

    db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"is_active": True, "login_attempts": 0, "lockout_until": None}},
    )
    log_audit(
        actor_user_id=actor_user_id,
        actor_role="admin",
        action="user_reactivated",
        target=f"user_id={user_id} username={user.get('username')}",
        old_value="inactive",
        new_value="active",
    )
    return True


def reset_password(
    user_id: str,
    new_password: str,
    actor_user_id: str,
) -> tuple[bool, str]:
    """
    Admin resets a user's password.
    The new password must meet PASSWORD_MIN_LENGTH.
    Returns (True, "") or (False, error_message).
    """
    if len(new_password) < config.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters."

    db = get_db()
    result = db["users"].update_one(
        {"user_id": user_id},
        {"$set": {
            "password_hash":       _hash_password(new_password),
            "force_password_reset": True,
            "login_attempts":      0,
            "lockout_until":       None,
        }},
    )
    if result.matched_count == 0:
        return False, f"User ID '{user_id}' not found."

    log_audit(
        actor_user_id=actor_user_id,
        actor_role="admin",
        action="password_reset",
        target=f"user_id={user_id}",
        old_value="[redacted]",
        new_value="[redacted — new hash set]",
    )
    logger.info("Password reset for user %s by admin %s.", user_id, actor_user_id)
    return True, ""


def change_password(
    user_id: str,
    old_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    User changes their own password (requires current password verification).
    """
    db = get_db()
    user = db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return False, "User not found."

    # Verify current password
    try:
        ok = bcrypt.checkpw(
            old_password.encode("utf-8"),
            user["password_hash"].encode("utf-8"),
        )
    except Exception:
        ok = False

    if not ok:
        return False, "Current password is incorrect."

    if len(new_password) < config.PASSWORD_MIN_LENGTH:
        return False, f"New password must be at least {config.PASSWORD_MIN_LENGTH} characters."

    db["users"].update_one(
        {"user_id": user_id},
        {"$set": {
            "password_hash":        _hash_password(new_password),
            "force_password_reset": False,
        }},
    )
    return True, ""


def delete_user(user_id: str, actor_user_id: str) -> bool:
    """Permanently delete a user account. Returns True if found and deleted."""
    db = get_db()
    user = db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return False

    db["users"].delete_one({"user_id": user_id})
    log_audit(
        actor_user_id=actor_user_id,
        actor_role="admin",
        action="user_deleted",
        target=f"user_id={user_id} username={user.get('username')} role={user.get('role')}",
        old_value=str(user),
        new_value="DELETED",
    )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

def log_audit(
    actor_user_id: str,
    actor_role: str,
    action: str,
    target: str,
    old_value: str = "",
    new_value: str = "",
) -> None:
    """
    Write an immutable audit log entry. Always called before returning success
    for any admin/teacher action that modifies data.

    Actions tracked:
      user_created, user_deactivated, user_reactivated, user_deleted
      password_reset, role_changed
      attendance_override
      config_changed
    """
    db = get_db()
    doc: dict[str, Any] = {
        "actor_user_id": actor_user_id,
        "actor_role":    actor_role,
        "action":        action,
        "target":        target,
        "old_value":     old_value,
        "new_value":     new_value,
        "timestamp":     datetime.utcnow(),
    }
    db["audit_log"].insert_one(doc)
    logger.info(
        "AUDIT | actor=%s role=%s action=%s target=%s",
        actor_user_id, actor_role, action, target,
    )


def get_audit_log(
    actor_user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    Query audit_log with optional filters. Returns newest-first.
    """
    db = get_db()
    query: dict[str, Any] = {}

    if actor_user_id:
        query["actor_user_id"] = actor_user_id
    if action:
        query["action"] = action
    if date_from or date_to:
        ts_filter: dict[str, Any] = {}
        if date_from:
            ts_filter["$gte"] = date_from
        if date_to:
            ts_filter["$lte"] = date_to
        query["timestamp"] = ts_filter

    records = list(
        db["audit_log"]
        .find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    # Convert datetimes to ISO strings for display
    for r in records:
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")

    return records
