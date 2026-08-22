"""
routers/alerts.py
==================
POST /alerts/send — send Telegram absentee alerts for a given date+session.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from notifications.telegram_bot import send_batch_alerts, send_absentee_alert
from database.db_operations import get_absentees
from dependencies import require_role, TokenData

router = APIRouter()


class AlertsRequest(BaseModel):
    date_str: Optional[str] = None
    session: str = "FN"
    student_ids: Optional[list[str]] = None  # None = send to all absentees


@router.post("/send")
async def send_alerts(
    body: AlertsRequest,
    current_user: TokenData = Depends(require_role("teacher", "admin")),
):
    """
    Send Telegram absentee alerts.

    - If student_ids is None: sends to ALL absentees for date+session.
    - If student_ids is provided: sends only to those specific students.
    """
    date_str = body.date_str or date.today().isoformat()

    absentees = get_absentees(date_str, body.session)

    if body.student_ids:
        # Filter to only requested students
        absentees = [a for a in absentees if a["student_id"] in body.student_ids]

    if not absentees:
        return {"message": "No absentees found for the specified date/session.", "results": []}

    results = send_batch_alerts(absentees, date_str, body.session)

    sent_count    = sum(1 for r in results if r["status"] == "sent")
    skipped_count = sum(1 for r in results if r["status"] == "skipped_no_chat_id")
    failed_count  = sum(1 for r in results if r["status"] == "failed")

    return {
        "message": f"Alerts processed: {sent_count} sent, {skipped_count} skipped (no chat_id), {failed_count} failed.",
        "summary": {"sent": sent_count, "skipped": skipped_count, "failed": failed_count},
        "results": results,
    }
