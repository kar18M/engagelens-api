# Pydantic models for student endpoints
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class StudentCreate(BaseModel):
    student_id: str
    name: str
    roll_no: str = ""
    class_section: str = ""
    parent_telegram_chat_id: Optional[str] = None


class StudentUpdate(BaseModel):
    name: str
    roll_no: str
    class_section: str


class StudentResponse(BaseModel):
    student_id: str
    name: str
    roll_no: str = ""
    class_section: str = ""
    parent_telegram_chat_id: Optional[str] = None
    enrolled_on: Optional[str] = None
    angles_enrolled: list[str] = []

    class Config:
        from_attributes = True
