"""
notifications/telegram_bot.py
==============================
Telegram absentee alert module for EngageLens Phase 9.

Public API:
  send_absentee_alert(student, date_str, session) -> dict
  send_batch_alerts(absentees, date_str, session) -> list[dict]

Design decisions:
  - Uses the Telegram Bot API directly via requests (no python-telegram-bot
    dependency) to keep the dependency surface minimal.
  - Token is read from config.TELEGRAM_BOT_TOKEN (which reads from env var).
  - Each send attempt is logged to notifications_log before returning.
  - send_batch_alerts never raises — per-student failures are captured in the
    result list so the UI can show partial success without crashing.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests

import config
from database.db_operations import log_notification, get_notification_log

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _format_date(date_str: str) -> str:
    """Convert '2026-07-29' → '29 July 2026' for the message body."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%-d %B %Y")   # e.g. "29 July 2026"
    except ValueError:
        return date_str


def _session_full(session: str) -> str:
    """Convert 'FN' → 'Forenoon', 'AN' → 'Afternoon'."""
    return "Forenoon" if session == "FN" else "Afternoon"


def send_absentee_alert(
    student: dict,
    date_str: str,
    session: str,
) -> dict:
    """
    Send one formal absentee alert to the student's linked parent via Telegram.

    Parameters
    ----------
    student   : Dict with keys: student_id, name, roll_no, class_section,
                parent_telegram_chat_id
    date_str  : ISO date string, e.g. "2026-07-29"
    session   : "FN" or "AN"

    Returns
    -------
    {
        "student_id"         : str,
        "status"             : "sent" | "failed" | "skipped_no_chat_id" | "already_sent",
        "telegram_message_id": int | None,
        "error"              : str | None,
    }
    """
    student_id = student["student_id"]

    # ── Guard: no parent chat_id linked ───────────────────────────────────────
    chat_id = student.get("parent_telegram_chat_id")
    if not chat_id:
        log_notification(student_id, date_str, session, "skipped_no_chat_id")
        return {
            "student_id":          student_id,
            "status":              "skipped_no_chat_id",
            "telegram_message_id": None,
            "error":               None,
        }

    # ── Guard: already sent for this (student, date, session) ────────────────
    existing = get_notification_log(student_id, date_str, session)
    if existing and existing.get("status") == "sent":
        return {
            "student_id":          student_id,
            "status":              "already_sent",
            "telegram_message_id": existing.get("telegram_message_id"),
            "error":               None,
        }

    # ── Build message ─────────────────────────────────────────────────────────
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        err = "TELEGRAM_BOT_TOKEN is not set — cannot send alerts."
        logger.error(err)
        log_notification(student_id, date_str, session, "failed")
        return {
            "student_id":          student_id,
            "status":              "failed",
            "telegram_message_id": None,
            "error":               err,
        }

    message_text = config.ABSENTEE_MESSAGE_TEMPLATE.format(
        name=student.get("name", student_id),
        roll_no=student.get("roll_no", student_id),
        class_section=student.get("class_section", "—"),
        session_full=_session_full(session),
        date_display=_format_date(date_str),
    )

    # ── Send via Telegram Bot API ─────────────────────────────────────────────
    url = TELEGRAM_API_BASE.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text":    message_text,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        if response.ok and data.get("ok"):
            msg_id = data["result"]["message_id"]
            log_notification(student_id, date_str, session, "sent", msg_id)
            logger.info(
                "Alert sent to parent of %s | msg_id=%s | session=%s",
                student_id, msg_id, session,
            )
            return {
                "student_id":          student_id,
                "status":              "sent",
                "telegram_message_id": msg_id,
                "error":               None,
            }
        else:
            # Telegram returned ok=False (e.g. bad token, blocked by user)
            err_desc = data.get("description", "Unknown Telegram error")
            logger.warning(
                "Telegram API error for student %s: %s", student_id, err_desc
            )
            log_notification(student_id, date_str, session, "failed")
            return {
                "student_id":          student_id,
                "status":              "failed",
                "telegram_message_id": None,
                "error":               err_desc,
            }

    except requests.exceptions.Timeout:
        err = "Telegram API timed out (10s). Check network connectivity."
        logger.error("Timeout sending alert for student %s: %s", student_id, err)
        log_notification(student_id, date_str, session, "failed")
        return {
            "student_id":          student_id,
            "status":              "failed",
            "telegram_message_id": None,
            "error":               err,
        }
    except requests.exceptions.RequestException as exc:
        err = f"Network error: {exc}"
        logger.error("RequestException for student %s: %s", student_id, exc)
        log_notification(student_id, date_str, session, "failed")
        return {
            "student_id":          student_id,
            "status":              "failed",
            "telegram_message_id": None,
            "error":               err,
        }


def send_batch_alerts(
    absentees: list[dict],
    date_str: str,
    session: str,
) -> list[dict]:
    """
    Send absentee alerts to all parents in the absentees list.

    Iterates over absentees one by one, never raises — each student's result
    is captured independently so a failure for one student doesn't block the rest.

    Parameters
    ----------
    absentees : list of student dicts (from get_absentees())
    date_str  : ISO date string
    session   : "FN" or "AN"

    Returns
    -------
    List of per-student result dicts (same schema as send_absentee_alert returns).
    """
    results = []
    for student in absentees:
        result = send_absentee_alert(student, date_str, session)
        results.append(result)
        logger.debug(
            "Batch alert result: student=%s status=%s",
            student["student_id"], result["status"],
        )
    return results
