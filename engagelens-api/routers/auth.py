"""
routers/auth.py
================
Authentication endpoints: login, current user, change password.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from auth.user_operations import get_user_by_username, change_password as db_change_password
from dependencies import create_access_token, get_current_user, TokenData
from models.auth import LoginRequest, TokenResponse, UserMeResponse, ChangePasswordRequest
import config
import bcrypt

router = APIRouter()


def _verify_credentials(username: str, password: str) -> dict:
    """Verify username/password and return user doc on success, raise HTTPException on failure."""
    from auth.user_operations import get_user_by_username, _backend, _get_supabase, _get_mongo_db
    from datetime import datetime

    username = username.strip().lower()
    user = get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated.")

    lockout_field = user.get("locked_until") or user.get("lockout_until")
    if lockout_field and datetime.utcnow() < datetime.fromisoformat(str(lockout_field).replace("Z", "+00:00").replace("+00:00", "")) if isinstance(lockout_field, str) else False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account temporarily locked.")

    stored_hash = user.get("password_hash", "")
    try:
        pw_ok = bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        pw_ok = False

    if not pw_ok:
        # Record failed attempt
        if _backend == "supabase":
            sb = _get_supabase()
            attempts = (user.get("failed_attempts") or 0) + 1
            sb.table("users").update({"failed_attempts": attempts}).eq("user_id", user["user_id"]).execute()
        else:
            from datetime import timedelta
            db = _get_mongo_db()
            attempts = user.get("login_attempts", 0) + 1
            update = {"login_attempts": attempts}
            if attempts >= config.MAX_LOGIN_ATTEMPTS:
                update["lockout_until"] = datetime.utcnow() + timedelta(minutes=config.LOCKOUT_DURATION_MINUTES)
            db["users"].update_one({"user_id": user["user_id"]}, {"$set": update})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    # Record successful login
    if _backend == "supabase":
        sb = _get_supabase()
        sb.table("users").update({"last_login": datetime.utcnow().isoformat(), "failed_attempts": 0}).eq("user_id", user["user_id"]).execute()
    else:
        db = _get_mongo_db()
        db["users"].update_one(
            {"user_id": user["user_id"]},
            {"$set": {"last_login": datetime.utcnow(), "login_attempts": 0, "lockout_until": None}},
        )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(form: LoginRequest):
    """Authenticate and return a JWT token."""
    user = _verify_credentials(form.username, form.password)
    token_data = {
        "user_id":           user["user_id"],
        "username":          user["username"],
        "role":              user["role"],
        "full_name":         user.get("full_name", user["username"]),
        "assigned_sections": user.get("assigned_sections", []),
        "linked_student_id": user.get("linked_student_id"),
    }
    access_token = create_access_token(token_data)
    return TokenResponse(
        access_token=access_token,
        role=user["role"],
        full_name=user.get("full_name", user["username"]),
        user_id=user["user_id"],
    )


@router.post("/login/form", response_model=TokenResponse)
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    """OAuth2-compatible form login (for /docs Swagger UI)."""
    user = _verify_credentials(form.username, form.password)
    token_data = {
        "user_id":           user["user_id"],
        "username":          user["username"],
        "role":              user["role"],
        "full_name":         user.get("full_name", user["username"]),
        "assigned_sections": user.get("assigned_sections", []),
        "linked_student_id": user.get("linked_student_id"),
    }
    access_token = create_access_token(token_data)
    return TokenResponse(
        access_token=access_token,
        role=user["role"],
        full_name=user.get("full_name", user["username"]),
        user_id=user["user_id"],
    )


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return UserMeResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        assigned_sections=current_user.assigned_sections,
        linked_student_id=current_user.linked_student_id,
    )


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """Authenticated user changes their own password."""
    ok, msg = db_change_password(current_user.user_id, body.old_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"message": "Password changed successfully."}
