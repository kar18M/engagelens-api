"""
auth/auth_manager.py
=====================
Core authentication functions for EngageLens Phase 10.

Responsibilities:
  - Login: bcrypt verification, is_active check, rate limiting, session state setup
  - Logout: clear all session state keys
  - Session timeout: idle auto-logout after SESSION_TIMEOUT_MINUTES
  - Role guard: require_role() checks role at top of every portal page
  - Activity tracking: update_last_activity() refreshes the timeout clock

Design note:
  We use st.session_state exclusively (no cookies, no JWT).
  This is appropriate for a college-project scope running on a local/LAN server.
  For a production multi-user cloud deployment you would add signed cookies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import streamlit as st

import config

logger = logging.getLogger(__name__)

# ── Keys stored in st.session_state ──────────────────────────────────────────
_SESSION_KEYS = [
    "authenticated",
    "role",
    "user_id",
    "username",
    "full_name",
    "assigned_sections",   # teacher only
    "linked_student_id",   # student only
    "last_activity",
    "timeout_triggered",
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    """Return True if a valid, non-expired session exists."""
    return bool(st.session_state.get("authenticated", False))


def get_current_user() -> dict:
    """Return the current user's session info dict (safe subset, no password)."""
    return {
        "user_id":           st.session_state.get("user_id", ""),
        "username":          st.session_state.get("username", ""),
        "full_name":         st.session_state.get("full_name", ""),
        "role":              st.session_state.get("role", ""),
        "assigned_sections": st.session_state.get("assigned_sections", []),
        "linked_student_id": st.session_state.get("linked_student_id"),
    }


def check_session_timeout() -> None:
    """
    Check if the session has been idle for more than SESSION_TIMEOUT_MINUTES.
    If so, clear session and rerun so the user sees the login page.
    Call this at the top of every portal page BEFORE rendering anything.
    """
    if not is_authenticated():
        return

    last = st.session_state.get("last_activity")
    if last is None:
        _do_logout()
        return

    elapsed = datetime.utcnow() - last
    if elapsed > timedelta(minutes=config.SESSION_TIMEOUT_MINUTES):
        logger.info(
            "Session timeout for user %s after %.1f minutes of inactivity.",
            st.session_state.get("username", "?"),
            elapsed.total_seconds() / 60,
        )
        _do_logout(timeout=True)
        st.rerun()


def update_last_activity() -> None:
    """Refresh the idle-timeout clock. Call after check_session_timeout()."""
    st.session_state["last_activity"] = datetime.utcnow()


def require_role(*allowed_roles: str) -> None:
    """
    Defense-in-depth role guard. Place at the top of every portal page function
    (after check_session_timeout and update_last_activity).

    If the user is not authenticated or their role is not in allowed_roles,
    shows an error and calls st.stop() so no portal content is rendered.

    Example usage (at the very top of a portal page):
        from auth.auth_manager import require_role, check_session_timeout, update_last_activity
        check_session_timeout()
        require_role("teacher")
        update_last_activity()
    """
    if not is_authenticated():
        st.error("🔒 You must be logged in to view this page.", icon="🔴")
        st.page_link("login.py", label="Go to Login", icon="🔑")
        st.stop()

    role = st.session_state.get("role", "")
    if role not in allowed_roles:
        st.error(
            f"🚫 **Unauthorized.** This page requires role: "
            f"`{'` or `'.join(allowed_roles)}`. Your role: `{role}`.",
            icon="🚫",
        )
        st.stop()


def login(username: str, password: str) -> tuple[bool, str]:
    """
    Attempt login. Validates against the `users` MongoDB collection.

    Steps:
      1. Fetch user document by username.
      2. Check is_active.
      3. Check lockout (failed attempt count + lockout_until).
      4. bcrypt.checkpw — if wrong, increment attempt counter.
      5. On success: populate st.session_state, update last_login, reset attempts.

    Returns
    -------
    (True, "") on success.
    (False, error_message) on any failure.
    """
    from auth.user_operations import get_user_by_username
    import bcrypt

    username = username.strip().lower()

    if not username or not password:
        return False, "Username and password are required."

    user = get_user_by_username(username)
    if user is None:
        # Don't reveal whether the username exists
        return False, "Invalid username or password."

    # ── is_active check ───────────────────────────────────────────────────────
    if not user.get("is_active", True):
        return False, "This account has been deactivated. Contact your administrator."

    # ── Lockout check ─────────────────────────────────────────────────────────
    lockout_until = user.get("lockout_until")
    if lockout_until and datetime.utcnow() < lockout_until:
        remaining = int((lockout_until - datetime.utcnow()).total_seconds() / 60) + 1
        return False, (
            f"Account temporarily locked after too many failed attempts. "
            f"Try again in {remaining} minute(s)."
        )

    # ── Password verification ─────────────────────────────────────────────────
    stored_hash = user.get("password_hash", "")
    try:
        pw_ok = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception as exc:
        logger.error("bcrypt error during login for %s: %s", username, exc)
        pw_ok = False

    if not pw_ok:
        _record_failed_attempt(user)
        attempts = user.get("login_attempts", 0) + 1
        remaining_attempts = config.MAX_LOGIN_ATTEMPTS - attempts
        if remaining_attempts <= 0:
            return False, (
                f"Too many failed attempts. Account locked for "
                f"{config.LOCKOUT_DURATION_MINUTES} minutes."
            )
        return False, (
            f"Invalid username or password. "
            f"{remaining_attempts} attempt(s) remaining before lockout."
        )

    # ── Success — populate session state ──────────────────────────────────────
    _populate_session(user)
    _record_successful_login(user)
    logger.info("Login success: %s (role=%s)", username, user["role"])
    return True, ""


def logout() -> None:
    """Public logout — clears session and forces rerun to show login page."""
    _do_logout()
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _do_logout(timeout: bool = False) -> None:
    """Clear all session state keys."""
    for key in _SESSION_KEYS:
        st.session_state.pop(key, None)
    if timeout:
        st.session_state["timeout_triggered"] = True


def _populate_session(user: dict) -> None:
    """Write user fields into st.session_state after successful login."""
    st.session_state["authenticated"]     = True
    st.session_state["role"]              = user["role"]
    st.session_state["user_id"]           = user["user_id"]
    st.session_state["username"]          = user["username"]
    st.session_state["full_name"]         = user.get("full_name", user["username"])
    st.session_state["assigned_sections"] = user.get("assigned_sections", [])
    st.session_state["linked_student_id"] = user.get("linked_student_id")
    st.session_state["last_activity"]     = datetime.utcnow()
    st.session_state.pop("timeout_triggered", None)


def _record_failed_attempt(user: dict) -> None:
    """Increment login_attempts and set lockout_until if max reached."""
    from database.mongo_client import get_db
    db = get_db()

    attempts = user.get("login_attempts", 0) + 1
    update: dict = {"login_attempts": attempts}

    if attempts >= config.MAX_LOGIN_ATTEMPTS:
        update["lockout_until"] = datetime.utcnow() + timedelta(
            minutes=config.LOCKOUT_DURATION_MINUTES
        )
        logger.warning(
            "Account %s locked after %d failed attempts.", user["username"], attempts
        )

    db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": update},
    )


def _record_successful_login(user: dict) -> None:
    """Reset attempt counter and record last_login timestamp."""
    from database.mongo_client import get_db
    db = get_db()
    db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "last_login":     datetime.utcnow(),
            "login_attempts": 0,
            "lockout_until":  None,
        }},
    )
