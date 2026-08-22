"""
engagelens-api/dependencies.py
================================
JWT authentication middleware for FastAPI.

Endpoints that require a logged-in user depend on `get_current_user`.
Endpoints that require a specific role use `require_role("teacher")` etc.

Token flow:
  1. Client POSTs credentials to /auth/login → receives access_token (JWT)
  2. Client attaches header:  Authorization: Bearer <token>
  3. FastAPI routes with `Depends(get_current_user)` decode and validate the token.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# ── JWT Settings ──────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("ENGAGELENS_JWT_SECRET", "engagelens-super-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8-hour token (a school day)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class TokenData(BaseModel):
    user_id: str
    username: str
    role: str
    full_name: str
    assigned_sections: list[str] = []
    linked_student_id: Optional[str] = None


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token from the given payload dict."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Token validation ──────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Decode and validate the JWT bearer token.
    Raises HTTP 401 if token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return TokenData(
            user_id=user_id,
            username=payload.get("username", ""),
            role=payload.get("role", ""),
            full_name=payload.get("full_name", ""),
            assigned_sections=payload.get("assigned_sections", []),
            linked_student_id=payload.get("linked_student_id"),
        )
    except JWTError:
        raise credentials_exception


def require_role(*allowed_roles: str):
    """
    Returns a FastAPI dependency that enforces role-based access.

    Usage:
        @router.get("/admin-only")
        async def admin_page(user: TokenData = Depends(require_role("admin"))):
            ...
    """
    def _check(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {list(allowed_roles)}. Your role: {current_user.role}",
            )
        return current_user
    return _check
