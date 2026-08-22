# Pydantic models for auth
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: str


class UserMeResponse(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: str
    assigned_sections: list[str] = []
    linked_student_id: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
