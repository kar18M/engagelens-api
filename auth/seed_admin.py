"""
auth/seed_admin.py
===================
One-time bootstrap script to create the first Admin account and
auto-generate Student portal accounts for all already-enrolled students.

Run ONCE from the project root (with venv active):
    python auth/seed_admin.py

What this script does:
  1. Prompts for admin username + password (with confirmation).
  2. Inserts the admin user into MongoDB `users` collection.
  3. Reads ALL existing documents in `students` collection.
  4. Creates a student portal account for each:
       username        = student_id.lower()   (e.g. "24adr064")
       default password = student_id          (e.g. "24ADR064")
       linked_student_id = student_id
  5. Prints a summary table.

Students can change their passwords after first login.
"""

import getpass
import sys
from pathlib import Path

# ── Make sure project root is on sys.path ──────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from database.mongo_client import get_db, MongoConnectionError
from auth.user_operations import create_user


def _prompt_password(prompt: str) -> str:
    """Prompt for a password with confirmation loop."""
    while True:
        pw1 = getpass.getpass(prompt)
        if len(pw1) < 8:
            print("❌  Password must be at least 8 characters. Try again.")
            continue
        pw2 = getpass.getpass("   Confirm password: ")
        if pw1 != pw2:
            print("❌  Passwords do not match. Try again.")
            continue
        return pw1


def seed_admin():
    print("\n" + "=" * 60)
    print("  EngageLens Phase 10 — Admin Bootstrap")
    print("=" * 60)

    # ── Check MongoDB connection ───────────────────────────────────────────────
    try:
        db = get_db()
        print("✅  MongoDB connected.")
    except MongoConnectionError as exc:
        print(f"❌  MongoDB error: {exc}")
        sys.exit(1)

    # ── Check for existing admin ───────────────────────────────────────────────
    existing_admins = list(db["users"].find({"role": "admin"}, {"username": 1, "_id": 0}))
    if existing_admins:
        print(
            f"\n⚠️  Admin account(s) already exist: "
            f"{[a['username'] for a in existing_admins]}"
        )
        proceed = input("   Create another admin anyway? [y/N]: ").strip().lower()
        if proceed != "y":
            print("   Skipping admin creation.")
        else:
            _create_admin_interactive(db)
    else:
        _create_admin_interactive(db)

    # ── Auto-create student accounts ──────────────────────────────────────────
    print("\n" + "-" * 60)
    print("  Auto-creating Student Portal Accounts")
    print("-" * 60)

    students = list(db["students"].find({}, {"_id": 0, "face_encodings": 0}))
    if not students:
        print("ℹ️   No enrolled students found. Skipping student account creation.")
    else:
        print(f"Found {len(students)} enrolled student(s).\n")
        created = 0
        skipped = 0

        for stu in students:
            sid      = stu["student_id"]
            name     = stu.get("name", sid)
            username = sid.lower()
            password = sid  # default password = student_id

            # Check if account already exists
            if db["users"].find_one({"username": username}):
                print(f"   ⏭️  Skip  — {name} ({sid}): username '{username}' already exists")
                skipped += 1
                continue

            ok, result = create_user(
                username=username,
                password=password,
                role="student",
                full_name=name,
                email="",
                linked_student_id=sid,
                assigned_sections=[],
                created_by="seed_admin",
            )
            if ok:
                print(f"   ✅  Created — {name} ({sid}) → username: {username}  |  default password: {sid}")
                created += 1
            else:
                print(f"   ❌  Failed  — {name} ({sid}): {result}")

        print(f"\n{'=' * 60}")
        print(f"  Student accounts: {created} created, {skipped} skipped")

    print("\n" + "=" * 60)
    print("  Bootstrap complete!  Run the app with:  bash run.sh")
    print("=" * 60 + "\n")


def _create_admin_interactive(db):
    print("\n  Create Admin Account")
    print("  --------------------")

    while True:
        username = input("  Admin username: ").strip().lower()
        if not username:
            print("  ❌  Username cannot be blank.")
            continue
        if db["users"].find_one({"username": username}):
            print(f"  ❌  Username '{username}' already exists. Choose another.")
            continue
        break

    full_name = input("  Full name (optional): ").strip() or username
    email     = input("  Email (optional): ").strip()

    password = _prompt_password("  Admin password (min 8 chars): ")

    ok, result = create_user(
        username=username,
        password=password,
        role="admin",
        full_name=full_name,
        email=email,
        linked_student_id=None,
        assigned_sections=[],
        created_by="seed_admin",
    )
    if ok:
        print(f"\n  ✅  Admin account created!")
        print(f"     Username : {username}")
        print(f"     Full name: {full_name}")
        print(f"     User ID  : {result}")
    else:
        print(f"\n  ❌  Failed to create admin: {result}")


if __name__ == "__main__":
    seed_admin()
