"""
scripts/migrate_classes.py
===========================
One-time migration script.

What it does:
  1. Renames every student's class_section → "| AIDS - B"
     (propagates to attendance records too).
  2. Seeds the 'classes' collection with:
       - "| AIDS - A"
       - "| AIDS - B"
       - "| AIDS - C"

Run from the project root:
    python scripts/migrate_classes.py

Safe to run multiple times (idempotent).
"""

import sys
import os
from datetime import datetime

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.mongo_client import get_db

TARGET_SECTION = "| AIDS - B"
SEED_CLASSES   = ["| AIDS - A", "| AIDS - B", "| AIDS - C"]

def run():
    db = get_db()

    # ── 1. Show what currently exists ────────────────────────────────────────
    existing_sections = list(db["students"].distinct("class_section"))
    total_students    = db["students"].count_documents({})
    print(f"\n{'='*60}")
    print(f"  EngageLens — Class Migration")
    print(f"{'='*60}")
    print(f"  Students found : {total_students}")
    print(f"  Current sections: {existing_sections or ['(none)']}")
    print(f"  Target section  : {TARGET_SECTION}")
    print(f"{'='*60}\n")

    # ── 2. Remap all students → TARGET_SECTION ───────────────────────────────
    result = db["students"].update_many(
        {},
        {"$set": {"class_section": TARGET_SECTION}},
    )
    print(f"[students]   Updated {result.modified_count} / {total_students} records "
          f"→ class_section = '{TARGET_SECTION}'")

    # Propagate to attendance (denormalised field)
    att_result = db["attendance"].update_many(
        {},
        {"$set": {"class_section": TARGET_SECTION}},
    )
    print(f"[attendance] Updated {att_result.modified_count} attendance records "
          f"→ class_section = '{TARGET_SECTION}'")

    # Also update users.assigned_sections that contain old section names
    # (teachers / students whose user account references an old section)
    users_cursor = db["users"].find(
        {"assigned_sections": {"$exists": True, "$ne": []}},
        {"_id": 0, "user_id": 1, "assigned_sections": 1, "role": 1},
    )
    users_updated = 0
    for u in users_cursor:
        old_secs = u.get("assigned_sections", [])
        # If any section is NOT one of the seed classes, remap to TARGET_SECTION
        new_secs = []
        changed  = False
        for s in old_secs:
            if s in SEED_CLASSES:
                new_secs.append(s)
            else:
                new_secs.append(TARGET_SECTION)
                changed = True
        if changed:
            db["users"].update_one(
                {"user_id": u["user_id"]},
                {"$set": {"assigned_sections": list(set(new_secs))}},
            )
            users_updated += 1
    print(f"[users]      Updated {users_updated} user account(s) → assigned_sections remapped")

    # ── 3. Seed classes collection ────────────────────────────────────────────
    print(f"\nSeeding 'classes' collection …")
    import uuid
    seeded = 0
    skipped = 0
    for class_name in SEED_CLASSES:
        if db["classes"].find_one({"name": class_name}):
            print(f"  SKIP  '{class_name}' — already exists")
            skipped += 1
            continue
        class_id = f"CLS-{uuid.uuid4().hex[:8].upper()}"
        db["classes"].insert_one({
            "class_id":   class_id,
            "name":       class_name,
            "created_by": "migration",
            "created_on": datetime.utcnow(),
        })
        print(f"  OK    '{class_name}' → {class_id}")
        seeded += 1

    print(f"\n[classes]    {seeded} created, {skipped} already existed")

    # ── 4. Verify ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  Verification")
    print(f"{'='*60}")
    for cls in db["classes"].find({}, {"_id": 0}).sort("name", 1):
        cnt = db["students"].count_documents({"class_section": cls["name"]})
        print(f"  {cls['name']:30s}  →  {cnt} student(s)")
    print(f"{'='*60}")
    print("  Migration complete ✅\n")


if __name__ == "__main__":
    run()
