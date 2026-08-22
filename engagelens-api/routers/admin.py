"""
routers/admin.py
=================
Admin-only endpoints: user management, audit log, system health.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import sys
import platform
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from auth.user_operations import (
    create_user, get_all_users, get_user_by_id,
    update_user, delete_user, deactivate_user,
    reactivate_user, reset_password, get_audit_log,
)
from dependencies import require_role, TokenData
import config

router = APIRouter()


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: str
    email: str = ""
    linked_student_id: Optional[str] = None
    assigned_sections: list[str] = []


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    assigned_sections: Optional[list[str]] = None
    linked_student_id: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str


# ── User Management ───────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    role: Optional[str] = None,
    current_user: TokenData = Depends(require_role("admin")),
):
    """List all users, optionally filtered by role."""
    return get_all_users(role_filter=role)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: UserCreateRequest,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Create a new user account."""
    ok, result = create_user(
        username=body.username,
        password=body.password,
        role=body.role,
        full_name=body.full_name,
        email=body.email,
        linked_student_id=body.linked_student_id,
        assigned_sections=body.assigned_sections,
        created_by=current_user.user_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"user_id": result, "message": "User created successfully."}


@router.put("/users/{user_id}")
async def update_user_endpoint(
    user_id: str,
    body: UserUpdateRequest,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Update user fields."""
    fields = {k: v for k, v in body.dict().items() if v is not None}
    ok = update_user(user_id, fields, actor_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
    return {"message": "User updated."}


@router.delete("/users/{user_id}")
async def delete_user_endpoint(
    user_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Permanently delete a user."""
    ok = delete_user(user_id, actor_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")
    return {"message": "User deleted."}


@router.post("/users/{user_id}/deactivate")
async def deactivate(user_id: str, current_user: TokenData = Depends(require_role("admin"))):
    ok = deactivate_user(user_id, actor_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": "User deactivated."}


@router.post("/users/{user_id}/reactivate")
async def reactivate(user_id: str, current_user: TokenData = Depends(require_role("admin"))):
    ok = reactivate_user(user_id, actor_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": "User reactivated."}


@router.post("/users/{user_id}/reset-password")
async def reset_pw(
    user_id: str,
    body: ResetPasswordRequest,
    current_user: TokenData = Depends(require_role("admin")),
):
    ok, msg = reset_password(user_id, body.new_password, actor_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": "Password reset successfully."}


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit")
async def audit_log(
    limit: int = 100,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Return the most recent admin audit log entries."""
    return get_audit_log(limit=limit)


# ── System Health ─────────────────────────────────────────────────────────────

@router.get("/health")
async def system_health(current_user: TokenData = Depends(require_role("admin", "teacher"))):
    """Return basic system health information."""
    import psutil
    import os
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
    except Exception:
        cpu_percent = -1
        mem = None
        disk = None

    _backend = os.environ.get("DB_BACKEND", "mongo").strip().lower()
    db_status = "unknown"
    student_count = -1
    attendance_count = -1

    if _backend == "supabase":
        try:
            from database.supabase_client import get_supabase
            sb = get_supabase()
            s_res = sb.table("students").select("*", count="exact").execute()
            a_res = sb.table("attendance").select("*", count="exact").execute()
            student_count = s_res.count or 0
            attendance_count = a_res.count or 0
            db_status = "connected (supabase)"
        except Exception as e:
            db_status = f"supabase error: {e}"
    else:
        try:
            from database.mongo_client import get_db
            db = get_db()
            db.command("ping")
            student_count = db["students"].count_documents({})
            attendance_count = db["attendance"].count_documents({})
            db_status = "connected (mongodb)"
        except Exception as e:
            db_status = f"mongodb error: {e}"

    return {
        "server": {
            "python_version": platform.python_version(),
            "os": platform.system(),
            "hostname": platform.node(),
        },
        "cpu_percent": cpu_percent,
        "memory": {
            "total_gb": round(mem.total / 1e9, 2) if mem else None,
            "used_gb":  round(mem.used / 1e9, 2) if mem else None,
            "percent":  mem.percent if mem else None,
        } if mem else None,
        "disk": {
            "total_gb": round(disk.total / 1e9, 2) if disk else None,
            "used_gb":  round(disk.used / 1e9, 2) if disk else None,
            "percent":  disk.percent if disk else None,
        } if disk else None,
        "database": {
            "status": db_status,
            "students_enrolled": student_count,
            "attendance_records": attendance_count,
        },
    }
