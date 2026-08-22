"""
database/supabase_client.py
============================
Supabase (PostgreSQL) connection factory for EngageLens.

Replaces mongo_client.py for cloud-database deployments.
Uses the supabase-py SDK which communicates via the Supabase REST API —
no direct PostgreSQL port (5432) needs to be open.

Usage:
    from database.supabase_client import get_supabase

Credentials are read from environment variables (set in .env):
    SUPABASE_URL          — https://<project-ref>.supabase.co
    SUPABASE_ANON_KEY     — anon/public JWT key  (for APK / browser clients)
    SUPABASE_SERVICE_KEY  — service_role key      (for FastAPI backend only)

The backend (FastAPI / Streamlit) should always use the SERVICE KEY so that
Row Level Security policies are bypassed and all rows are accessible.
The Flutter APK uses the ANON KEY (RLS enforces per-user visibility).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseConnectionError(RuntimeError):
    """Raised when EngageLens cannot initialise the Supabase client."""


@lru_cache(maxsize=1)
def _get_client() -> Client:
    """
    Return a cached Supabase Client.
    lru_cache ensures a single client is created per process lifetime.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    # Prefer service key for backend; fall back to anon key
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )

    if not url or not key:
        raise SupabaseConnectionError(
            "SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) "
            "must be set in the environment / .env file.\n"
            "Add them to .env:\n"
            "  SUPABASE_URL=https://<ref>.supabase.co\n"
            "  SUPABASE_SERVICE_KEY=<your-service-role-key>"
        )

    try:
        client: Client = create_client(url, key)
        logger.info("Supabase client initialised → %s", url)
        return client
    except Exception as exc:
        raise SupabaseConnectionError(
            f"Failed to create Supabase client: {exc}"
        ) from exc


def get_supabase() -> Client:
    """
    Return the cached Supabase Client instance.
    Raises SupabaseConnectionError if credentials are missing/invalid.
    """
    return _get_client()
