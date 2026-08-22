"""
routers/classes.py
====================
CRUD endpoints for class sections.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from database.db_operations import (
    get_all_classes,
    get_class_sections,
    create_class,
    delete_class,
)
from dependencies import get_current_user, require_role, TokenData

router = APIRouter()


class ClassCreateRequest(BaseModel):
    name: str


@router.get("/")
async def list_classes(current_user: TokenData = Depends(get_current_user)):
    """Return all classes."""
    return get_all_classes()


@router.get("/sections")
async def list_sections(current_user: TokenData = Depends(get_current_user)):
    """Return a flat list of class section name strings (for dropdowns)."""
    return get_class_sections()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_new_class(
    body: ClassCreateRequest,
    current_user: TokenData = Depends(require_role("admin", "teacher")),
):
    """Create a new class section."""
    ok, result = create_class(body.name, created_by=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return {"class_id": result, "name": body.name, "message": "Class created."}


@router.delete("/{class_id}")
async def remove_class(
    class_id: str,
    current_user: TokenData = Depends(require_role("admin")),
):
    """Delete a class. Blocked if students are still assigned to it."""
    ok, msg = delete_class(class_id, actor=current_user.user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": f"Class '{class_id}' deleted."}
