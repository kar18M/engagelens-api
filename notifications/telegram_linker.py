"""
notifications/telegram_linker.py
==================================
Background polling thread that listens for /start {student_id} messages from
parents and writes their chat_id into the student's MongoDB record.

Why a background thread instead of a separate process?
  - Simpler lifecycle: the thread is a daemon tied to the Streamlit process,
    so it starts and stops automatically with the app — no extra terminal or
    process manager needed.
  - No inter-process communication required: it writes directly to MongoDB
    using the same connection pool as the rest of the app.
  - At this scale (one institution, dozens of students) a single long-polling
    thread consumes negligible resources. A production deployment with many
    concurrent bots would use a proper webhook server instead.

The thread is started once from app.py via start_linker_thread().
A module-level _started flag ensures it is never started twice even if
app.py is re-imported by Streamlit's hot-reload mechanism.

How parent linking works:
  1. Teacher shares the deep link https://t.me/{BOT_USERNAME}?start={student_id}
     or its QR code with the parent.
  2. Parent clicks the link, Telegram opens the bot and sends "/start {student_id}"
     automatically.
  3. This poller receives that message, extracts student_id, writes the sender's
     chat_id to students.parent_telegram_chat_id.
  4. The Enroll Student page shows a live "✅ Parent linked" badge by refreshing
     the student document from MongoDB.
"""

from __future__ import annotations

import logging
import threading
import time

import requests

import config
from database.db_operations import get_student_by_id, update_student_chat_id

logger = logging.getLogger(__name__)

# Module-level guard — prevents double-start on Streamlit hot-reload
_started = False
_lock    = threading.Lock()

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _is_telegram_reachable() -> bool:
    """Quick connectivity probe — tries a HEAD request to api.telegram.org."""
    try:
        requests.head("https://api.telegram.org", timeout=5)
        return True
    except Exception:
        return False


def _poll_loop() -> None:
    """
    Main polling loop.  Runs indefinitely as a daemon thread.
    Uses Telegram's getUpdates long-polling (timeout=20s) to avoid hammering
    the API.  Tracks the `offset` parameter so each update is processed once.

    If the network is unreachable (e.g. college WiFi blocking port 443),
    the loop backs off silently instead of flooding the terminal.
    """
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set — parent linking poller will not start. "
            "Set the env var and restart the app to enable Telegram linking."
        )
        return

    # ── Initial connectivity check ─────────────────────────────────────────────
    if not _is_telegram_reachable():
        logger.warning(
            "⚠️  Telegram is UNREACHABLE (network blocked — e.g. college/institution WiFi). "
            "Parent-linking and alert notifications will be disabled until connectivity is restored. "
            "The app continues to work normally for attendance tracking."
        )

    offset = 0
    _offline_logged = False   # track whether we already printed the offline message
    logger.info("Telegram linker polling thread started.")

    while True:
        try:
            url = TELEGRAM_API_BASE.format(token=token, method="getUpdates")
            params = {
                "offset":          offset,
                "timeout":         20,          # long-poll for up to 20 seconds
                "allowed_updates": ["message"],  # only care about text messages
            }
            resp = requests.get(url, params=params, timeout=30)

            # If we get here, we're online — reset offline flag
            _offline_logged = False

            if not resp.ok:
                logger.warning(
                    "getUpdates returned HTTP %s: %s", resp.status_code, resp.text[:200]
                )
                time.sleep(5)
                continue

            data = resp.json()
            if not data.get("ok"):
                logger.warning("getUpdates ok=False: %s", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                update_id = update["update_id"]
                offset = update_id + 1   # acknowledge this update

                msg  = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if not text.startswith("/start"):
                    continue

                # Extract student_id from "/start <student_id>"
                parts = text.split(maxsplit=1)
                if len(parts) < 2 or not parts[1].strip():
                    # Plain /start with no payload — ignore
                    continue

                student_id = parts[1].strip()
                logger.info(
                    "Received /start from chat_id=%s with student_id=%s",
                    chat_id, student_id,
                )

                # Validate student exists before writing
                student = get_student_by_id(student_id)
                if student is None:
                    logger.warning(
                        "Parent linked with unknown student_id '%s' — ignoring.",
                        student_id,
                    )
                    _send_reply(
                        token, chat_id,
                        "❌ Student ID not recognised. Please contact the class teacher.",
                    )
                    continue

                # Write chat_id into the student record
                updated = update_student_chat_id(student_id, chat_id)
                if updated:
                    _send_reply(
                        token, chat_id,
                        f"✅ Linked successfully! You will now receive attendance alerts "
                        f"for {student['name']} ({student_id}).",
                    )
                else:
                    logger.error(
                        "Failed to write chat_id for student %s — update returned False.",
                        student_id,
                    )

        except requests.exceptions.Timeout:
            # Long-poll timed out with no new messages — this is normal, loop again
            continue
        except requests.exceptions.RequestException:
            # Network error (blocked firewall, no internet, etc.)
            # Log ONCE then go silent — don't spam the terminal every 10s
            if not _offline_logged:
                logger.warning(
                    "📵 Telegram unreachable (network blocked). "
                    "Retrying silently in the background every 60s. "
                    "Telegram features will resume automatically when connectivity is restored."
                )
                _offline_logged = True
            time.sleep(60)   # longer back-off when offline
        except Exception as exc:
            logger.exception("Unexpected error in Telegram linker poll loop: %s", exc)
            time.sleep(10)



def _send_reply(token: str, chat_id: str, text: str) -> None:
    """Send a short confirmation/error reply back to the parent's Telegram chat."""
    try:
        url = TELEGRAM_API_BASE.format(token=token, method="sendMessage")
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=8)
    except Exception as exc:
        logger.warning("Could not send reply to chat_id %s: %s", chat_id, exc)


def start_linker_thread() -> None:
    """
    Start the Telegram parent-linking background polling thread exactly once.
    Safe to call multiple times — guarded by _started flag + lock.
    Called from app.py on startup.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True

    thread = threading.Thread(
        target=_poll_loop,
        name="telegram-linker",
        daemon=True,   # dies automatically when Streamlit process exits
    )
    thread.start()
    logger.info("Telegram linker thread launched (daemon=True).")
