"""
scripts/migrate_mongo_to_supabase.py
======================================
One-time migration script: copies ALL data from local MongoDB → Supabase.

Collections migrated:
  classes           →  public.classes
  students          →  public.students          (face_encodings as JSONB list)
  attendance        →  public.attendance
  users             →  public.users
  notifications_log →  public.notifications_log
  audit_log         →  public.audit_log

Run with:
  cd /home/karthick/smart-attend-modify
  source venv/bin/activate
  python scripts/migrate_mongo_to_supabase.py

Safety:
  - Supabase tables are wiped first (truncate with CASCADE) then re-inserted.
  - MongoDB data is NEVER modified.
  - Re-runnable: safe to run again after fixing partial failures.
"""

import json
import os
import sys
from datetime import datetime, date

# ── Load .env ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ── MongoDB ───────────────────────────────────────────────────────────────────
import pymongo
from bson import ObjectId

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "engagelens"

# ── Supabase ──────────────────────────────────────────────────────────────────
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    or os.environ.get("SUPABASE_ANON_KEY", "").strip()
)
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def to_json_safe(obj):
    """Recursively make a MongoDB document JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, list):
        return [to_json_safe(i) for i in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def chunked(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def upsert_batch(table: str, rows: list[dict], conflict_col: str | None = None):
    """Insert rows in batches of 100. Uses upsert if conflict_col given."""
    inserted = 0
    for chunk in chunked(rows, 100):
        if conflict_col:
            result = sb.table(table).upsert(chunk, on_conflict=conflict_col).execute()
        else:
            result = sb.table(table).upsert(chunk).execute()
        inserted += len(chunk)
    return inserted


def truncate_table(table: str):
    """Delete all rows from a Supabase table."""
    # Use a filter that matches everything (id is always set)
    sb.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


# ── Connect MongoDB ───────────────────────────────────────────────────────────

print("=" * 60)
print("EngageLens  ·  MongoDB → Supabase Migration")
print("=" * 60)

mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
mongo_client.admin.command("ping")
mongo_db = mongo_client[DB_NAME]
print(f"\n✅ MongoDB connected  →  {MONGO_URI}{DB_NAME}")
print(f"✅ Supabase connected →  {SUPABASE_URL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLASSES
# ─────────────────────────────────────────────────────────────────────────────
print("── [1/6] classes ────────────────────────────────────────")
raw_classes = list(mongo_db["classes"].find({}))
print(f"   Found {len(raw_classes)} class(es) in MongoDB")

if raw_classes:
    truncate_table("classes")
    rows = []
    for doc in raw_classes:
        safe = to_json_safe(doc)
        rows.append({
            "class_id":   safe.get("class_id", f"CLS-{str(doc['_id'])[:8].upper()}"),
            "name":       safe["name"],
            "created_by": safe.get("created_by", "system"),
            "created_on": safe.get("created_on") or datetime.utcnow().isoformat(),
        })
    n = upsert_batch("classes", rows, conflict_col="class_id")
    print(f"   ✅ Migrated {n} class(es)")
else:
    print("   ⚠️  No classes to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# 2. STUDENTS  (face_encodings as JSONB list)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── [2/6] students ───────────────────────────────────────")
raw_students = list(mongo_db["students"].find({}))
print(f"   Found {len(raw_students)} student(s) in MongoDB")

student_ids_seen = set()
if raw_students:
    truncate_table("students")
    rows = []
    for doc in raw_students:
        safe = to_json_safe(doc)
        sid = safe["student_id"]
        if sid in student_ids_seen:
            print(f"   ⚠️  Duplicate student_id '{sid}' — skipping")
            continue
        student_ids_seen.add(sid)

        # face_encodings: each item has {angle, embedding (list of floats), photo_path}
        encodings = []
        for enc in safe.get("face_encodings", []):
            emb = enc.get("embedding", [])
            # numpy tolist() gives a plain Python list — already JSON-safe
            encodings.append({
                "angle":      enc.get("angle", "front"),
                "embedding":  emb if isinstance(emb, list) else list(emb),
                "photo_path": enc.get("photo_path", ""),
            })

        rows.append({
            "student_id":               sid,
            "name":                     safe["name"],
            "roll_no":                  safe.get("roll_no") or sid,
            "class_section":            safe.get("class_section", ""),
            "parent_telegram_chat_id":  safe.get("parent_telegram_chat_id"),
            "face_encodings":           encodings,
            "enrolled_on":              safe.get("enrolled_on") or datetime.utcnow().isoformat(),
        })
        print(f"   · {sid:15s}  {safe['name']:25s}  section={safe.get('class_section','–'):<12}  angles={len(encodings)}")

    n = upsert_batch("students", rows, conflict_col="student_id")
    print(f"   ✅ Migrated {n} student(s)")
else:
    print("   ⚠️  No students to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# 3. ATTENDANCE
# ─────────────────────────────────────────────────────────────────────────────
print("\n── [3/6] attendance ─────────────────────────────────────")
raw_attendance = list(mongo_db["attendance"].find({}))
print(f"   Found {len(raw_attendance)} attendance record(s) in MongoDB")

if raw_attendance:
    truncate_table("attendance")
    rows = []
    skipped = 0
    seen_keys = set()
    for doc in raw_attendance:
        safe = to_json_safe(doc)
        sid     = safe.get("student_id", "")
        d       = safe.get("date", "")
        session = safe.get("session", "FN")

        # Skip records whose student was not migrated (referential integrity)
        if sid not in student_ids_seen:
            skipped += 1
            continue

        # Deduplicate (student_id, date, session)
        key = (sid, d, session)
        if key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(key)

        # Normalise session — default to FN if unrecognised
        if session not in ("FN", "AN"):
            session = "FN"

        # Normalise status
        status = safe.get("status", "Present")
        if status not in ("Present", "Absent", "Override"):
            status = "Present"

        # Normalise timestamp — MongoDB may have stored "HH:MM:SS" or full ISO
        raw_ts = safe.get("timestamp") or ""
        if raw_ts and "T" not in raw_ts and len(raw_ts) <= 8:
            # It's just a time string "HH:MM:SS" — combine with the date field
            ts = f"{d}T{raw_ts}+00:00" if d else datetime.utcnow().isoformat()
        elif raw_ts:
            ts = raw_ts
        else:
            ts = datetime.utcnow().isoformat()

        rows.append({
            "student_id":     sid,
            "name":           safe.get("name", ""),
            "roll_no":        safe.get("roll_no") or sid,
            "class_section":  safe.get("class_section", ""),
            "date":           d,
            "session":        session,
            "timestamp":      ts,
            "status":         status,
            "matched_angle":  safe.get("matched_angle"),
            "match_distance": float(safe.get("match_distance", 0)) if safe.get("match_distance") is not None else None,
        })

    n = upsert_batch("attendance", rows, conflict_col="student_id,date,session")
    print(f"   ✅ Migrated {n} record(s)  (skipped {skipped} duplicates/orphans)")
else:
    print("   ⚠️  No attendance records to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# 4. USERS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── [4/6] users ──────────────────────────────────────────")
raw_users = list(mongo_db["users"].find({}))
print(f"   Found {len(raw_users)} user(s) in MongoDB")

if raw_users:
    truncate_table("users")
    rows = []
    seen_usernames = set()
    for doc in raw_users:
        safe = to_json_safe(doc)
        username = safe.get("username", "")
        if username in seen_usernames:
            print(f"   ⚠️  Duplicate username '{username}' — skipping")
            continue
        seen_usernames.add(username)

        role = safe.get("role", "student")
        if role not in ("student", "teacher", "admin"):
            role = "student"

        # student_id FK: only set if the student was migrated
        linked_sid = safe.get("student_id")
        if linked_sid and linked_sid not in student_ids_seen:
            linked_sid = None

        rows.append({
            "user_id":        safe.get("user_id") or f"USR-{str(doc['_id'])[:8].upper()}",
            "username":       username,
            "password_hash":  safe.get("password_hash", ""),
            "role":           role,
            "student_id":     linked_sid,
            "is_active":      bool(safe.get("is_active", True)),
            "created_on":     safe.get("created_on") or datetime.utcnow().isoformat(),
            "last_login":     safe.get("last_login"),
            "failed_attempts":int(safe.get("failed_attempts", 0)),
            "locked_until":   safe.get("locked_until"),
        })
        print(f"   · {username:20s}  role={role}")

    n = upsert_batch("users", rows, conflict_col="username")
    print(f"   ✅ Migrated {n} user(s)")
else:
    print("   ⚠️  No users to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# 5. NOTIFICATIONS_LOG
# ─────────────────────────────────────────────────────────────────────────────
print("\n── [5/6] notifications_log ──────────────────────────────")
raw_notifs = list(mongo_db["notifications_log"].find({}))
print(f"   Found {len(raw_notifs)} notification log(s) in MongoDB")

if raw_notifs:
    truncate_table("notifications_log")
    rows = []
    skipped = 0
    seen_notif_keys = set()
    for doc in raw_notifs:
        safe = to_json_safe(doc)
        sid     = safe.get("student_id", "")
        d       = safe.get("date", "")
        session = safe.get("session", "FN")

        if sid not in student_ids_seen:
            skipped += 1
            continue

        key = (sid, d, session)
        if key in seen_notif_keys:
            skipped += 1
            continue
        seen_notif_keys.add(key)

        if session not in ("FN", "AN"):
            session = "FN"

        status = safe.get("status", "sent")
        if status not in ("sent", "failed", "skipped_no_chat_id"):
            status = "sent"

        rows.append({
            "student_id":          sid,
            "date":                d,
            "session":             session,
            "sent_at":             safe.get("sent_at") or datetime.utcnow().isoformat(),
            "status":              status,
            "telegram_message_id": safe.get("telegram_message_id"),
        })

    n = upsert_batch("notifications_log", rows, conflict_col="student_id,date,session")
    print(f"   ✅ Migrated {n} notification log(s)  (skipped {skipped})")
else:
    print("   ⚠️  No notification logs to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# 6. AUDIT_LOG
# ─────────────────────────────────────────────────────────────────────────────
print("\n── [6/6] audit_log ──────────────────────────────────────")
raw_audit = list(mongo_db["audit_log"].find({}))
print(f"   Found {len(raw_audit)} audit log(s) in MongoDB")

if raw_audit:
    truncate_table("audit_log")
    rows = []
    for doc in raw_audit:
        safe = to_json_safe(doc)
        rows.append({
            "actor_user_id": safe.get("actor_user_id", "unknown"),
            "action":        safe.get("action", ""),
            "target_type":   safe.get("target_type"),
            "target_id":     safe.get("target_id"),
            "details":       safe.get("details") or {},
            "timestamp":     safe.get("timestamp") or datetime.utcnow().isoformat(),
        })

    n = upsert_batch("audit_log", rows)
    print(f"   ✅ Migrated {n} audit log(s)")
else:
    print("   ⚠️  No audit logs to migrate")


# ─────────────────────────────────────────────────────────────────────────────
# VERIFY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("Migration complete — Verifying Supabase row counts:")
print("=" * 60)
tables = ["classes", "students", "attendance", "users", "notifications_log", "audit_log"]
for t in tables:
    result = sb.table(t).select("*", count="exact").execute()
    print(f"  {t:20s}: {result.count} rows")

print("\n🎉 All data migrated to Supabase successfully!\n")
