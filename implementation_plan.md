# EngageLens — Flutter + FastAPI Mobile APK Plan

## Overview

The goal is to convert the existing **Streamlit Python app** into a proper
**Android APK** by splitting it into two separate projects:

1. **`engagelens-api/`** — A **FastAPI** Python backend. Reuses ALL existing
   face recognition, database, and auth logic verbatim. Only the UI layer
   (Streamlit) is replaced.
2. **`engagelens-app/`** — A **Flutter** mobile app. Replaces the Streamlit UI.
   Calls the FastAPI backend over HTTP.

The server (PC/Raspberry Pi) runs the FastAPI backend. The APK installed on the
smartboard connects to the server's IP. No face recognition runs on the phone —
it stays on the server where the big models live.

---

## Architecture Diagram

```
┌─────────────────────────────────┐       HTTP/JSON
│        Android APK              │ ◄──────────────► ┌──────────────────────────┐
│  (Flutter — engagelens-app)     │                  │  FastAPI Server           │
│                                 │                  │  (engagelens-api)         │
│  Login Screen                   │  POST /auth/login│                           │
│  Teacher Portal                 │  POST /recognize │  face_recognition_module/ │
│  ↳ Live Scan                    │  GET  /students  │  database/                │
│  ↳ Batch Scan                   │  POST /enroll    │  auth/                    │
│  ↳ Attendance Log               │  GET  /attendance│  notifications/           │
│  ↳ Alerts                       │  POST /alerts    │  MongoDB                  │
│  Student Portal                 │                  │                           │
│  ↳ Dashboard                    │                  │  (insightface, onnxrt,    │
│  ↳ Attendance History           │                  │   opencv, pymongo)        │
│  ↳ Profile                      │                  └──────────────────────────┘
│  Admin Portal                   │
│  ↳ User Management              │
│  ↳ Class Management             │
│  ↳ System Health                │
└─────────────────────────────────┘
```

---

## Part 1 — FastAPI Backend (`engagelens-api/`)

### What changes

The existing Python project stays **100% intact**. We add a new
`engagelens-api/` folder **beside** (not inside) the Streamlit project.
It imports from the existing modules using a shared path or symlink.

Alternatively (cleaner): copy `face_recognition_module/`, `database/`,
`auth/`, `notifications/`, `config.py` into `engagelens-api/` and keep
Streamlit running separately.

### New files to create

```
engagelens-api/
├── main.py                  ← FastAPI app + CORS setup
├── routers/
│   ├── auth.py              ← POST /auth/login, POST /auth/logout
│   ├── students.py          ← GET/POST/PUT/DELETE /students
│   ├── attendance.py        ← GET/POST /attendance
│   ├── recognition.py       ← POST /recognize (image → names)
│   ├── enroll.py            ← POST /enroll (image + student_id)
│   ├── alerts.py            ← POST /alerts/send
│   ├── admin.py             ← user mgmt, class mgmt, system health
│   └── classes.py           ← GET/POST/DELETE /classes
├── models/                  ← Pydantic request/response schemas
│   ├── auth.py
│   ├── student.py
│   ├── attendance.py
│   └── recognition.py
├── dependencies.py          ← JWT auth middleware (get_current_user)
├── requirements.txt         ← fastapi, uvicorn, python-jose, passlib + existing deps
└── run_api.sh               ← uvicorn main:app --host 0.0.0.0 --port 8000
```

### All API Endpoints (mapped from existing Streamlit pages)

| Method | Endpoint | Mapped From | Description |
|--------|----------|-------------|-------------|
| `POST` | `/auth/login` | `auth/auth_manager.py → login()` | Returns JWT token |
| `GET` | `/auth/me` | session state | Returns current user info |
| `GET` | `/students` | `db_operations.get_all_students()` | List all students |
| `GET` | `/students/{id}` | `db_operations.get_student_by_id()` | Single student |
| `POST` | `/students` | `db_operations.insert_student()` | Create student |
| `PUT` | `/students/{id}` | `db_operations.update_student_info()` | Update student info |
| `DELETE` | `/students/{id}` | `db_operations.delete_student()` | Delete student |
| `POST` | `/enroll` | `pages/4_Enroll_Student.py` + `face_recognition_module/enroll.py` | Enroll face (upload photo) |
| `POST` | `/recognize` | `face_recognition_module/detector.py` + `recognizer.py` | Send image → get recognized names |
| `POST` | `/attendance/mark` | `db_operations.mark_attendance_if_new()` | Mark one student present |
| `GET` | `/attendance` | `db_operations.get_attendance_by_date()` | Attendance log |
| `GET` | `/attendance/stats` | `db_operations.get_attendance_stats()` | Stats for dashboard |
| `GET` | `/attendance/absentees` | `db_operations.get_absentees()` | Absentee list |
| `POST` | `/alerts/send` | `notifications/` telegram logic | Send Telegram alerts |
| `GET` | `/classes` | `db_operations.get_class_sections()` | List classes |
| `POST` | `/classes` | `db_operations.create_class()` | Create class |
| `DELETE` | `/classes/{id}` | `db_operations.delete_class()` | Delete class |
| `GET` | `/admin/health` | `portals/admin_portal/system_health.py` | System health status |
| `GET` | `/admin/users` | `portals/admin_portal/user_management.py` | List all users |
| `POST` | `/admin/users` | user_management | Create user |
| `PUT` | `/admin/users/{id}` | user_management | Update user |
| `DELETE` | `/admin/users/{id}` | user_management | Delete user |

### Authentication

- FastAPI returns a **JWT token** on `/auth/login`
- All other endpoints require `Authorization: Bearer <token>` header
- Flutter stores token in `flutter_secure_storage`
- Token carries `role` (student/teacher/admin) for permission guards

### Image Upload for Recognition

The Flutter app sends a **multipart/form-data** image to `/recognize`:
- Flutter captures frame from camera using `camera` package
- Sends JPEG bytes to the API
- API runs InsightFace on server, returns list of `{name, student_id, bbox}`
- Flutter draws overlay boxes on the camera preview

---

## Part 2 — Flutter App (`engagelens-app/`)

### Project Creation Command
```bash
flutter create --org com.engagelens --platforms android engagelens-app
```

### Key Flutter Packages

| Package | Purpose |
|---------|---------|
| `dio` | HTTP client for API calls |
| `flutter_secure_storage` | Store JWT token securely |
| `camera` | Access device camera for live scan |
| `image_picker` | Pick photo from gallery (for enrollment) |
| `go_router` | Navigation & role-based routing |
| `riverpod` | State management |
| `fl_chart` | Charts for attendance dashboard |
| `cached_network_image` | Student photo display |
| `permission_handler` | Camera permission request |

### Flutter Folder Structure

```
lib/
├── main.dart                    ← App entry + theme
├── core/
│   ├── api_client.dart          ← Dio + base URL + JWT interceptor
│   ├── auth_provider.dart       ← Riverpod: login state, role
│   └── router.dart              ← GoRouter with role guards
├── models/
│   ├── student.dart
│   ├── attendance.dart
│   └── recognition_result.dart
├── screens/
│   ├── login_screen.dart        ← Maps from login.py
│   ├── teacher/
│   │   ├── teacher_home.dart    ← Sidebar / bottom nav
│   │   ├── live_scan_screen.dart    ← Maps from pages/1_Live_Attendance.py
│   │   ├── batch_scan_screen.dart   ← Maps from pages/2_Batch_Classroom_Scan.py
│   │   ├── attendance_log_screen.dart  ← Maps from pages/3_Attendance_Log.py
│   │   ├── enroll_screen.dart       ← Maps from pages/4_Enroll_Student.py
│   │   ├── alerts_screen.dart       ← Maps from portals/teacher_portal/alerts.py
│   │   └── override_screen.dart     ← Maps from portals/teacher_portal/override.py
│   ├── student/
│   │   ├── student_home.dart
│   │   ├── dashboard_screen.dart    ← Maps from portals/student_portal/dashboard.py
│   │   ├── history_screen.dart      ← Maps from portals/student_portal/history.py
│   │   └── profile_screen.dart      ← Maps from portals/student_portal/profile.py
│   └── admin/
│       ├── admin_home.dart
│       ├── user_management_screen.dart
│       ├── class_management_screen.dart
│       ├── system_health_screen.dart
│       └── audit_screen.dart
└── widgets/
    ├── face_overlay_painter.dart    ← CustomPainter for bboxes
    ├── attendance_tile.dart
    ├── student_card.dart
    └── role_badge.dart
```

### The Critical Screen — Live Scan (Camera + Recognition)

This is the hardest screen. Here's how it works:

```
Flutter CameraPreview (shows live feed)
        │
        │ (capture frame every 2 seconds)
        ▼
 image bytes (JPEG)
        │
        │ POST /recognize   (multipart upload)
        ▼
 FastAPI → InsightFace → returns [{name, bbox, distance}]
        │
        ▼
 Flutter draws CustomPainter boxes on top of CameraPreview
 (green box = recognised, red = unknown)
        │
        │ (for each recognised student)
        ▼
 POST /attendance/mark  (mark present)
```

**Why this works well on a smartboard:**
- The smartboard camera captures the classroom
- Flutter sends frames to the server (same WiFi LAN = fast)
- Boxes are drawn natively in Flutter (smooth)
- No face recognition on the Android device itself

---

## Implementation Phases

### Phase 1 — FastAPI Backend (Week 1)
1. Create `engagelens-api/` folder
2. Write `main.py` with CORS enabled
3. Implement `/auth/login` endpoint (reuse existing `auth_manager.py`)
4. Implement JWT middleware in `dependencies.py`
5. Implement `/students` CRUD endpoints
6. Implement `/attendance` endpoints
7. Implement `/recognize` endpoint (reuse `detector.py` + `recognizer.py`)
8. Implement `/enroll` endpoint (reuse `enroll.py`)
9. Implement `/admin` and `/classes` endpoints
10. Test all endpoints with Postman/curl

### Phase 2 — Flutter Foundation (Week 2)
1. Create Flutter project
2. Set up `go_router` with role-based routing
3. Set up `riverpod` for state management
4. Implement `api_client.dart` with Dio + JWT interceptor
5. Build `login_screen.dart` (username, password, role badge UI)
6. Build bottom navigation shell for Teacher/Student/Admin

### Phase 3 — Teacher Screens (Week 3)
1. Attendance Log screen (table + filters)
2. Live Scan screen (camera + bbox overlay)
3. Batch Scan screen (upload image or take photo)
4. Enroll Student screen (multi-angle photo capture)
5. Alerts screen (absentee list + send Telegram button)
6. Override screen (manual mark present/absent)

### Phase 4 — Student & Admin Screens (Week 4)
1. Student Dashboard (attendance % chart with `fl_chart`)
2. Student History (list view with date filter)
3. Student Profile
4. Admin: User Management
5. Admin: Class Management
6. Admin: System Health
7. Admin: Audit Log

### Phase 5 — Build & Deploy (Week 5)
1. Configure `AndroidManifest.xml` (camera, internet permissions)
2. Set server base URL as a build-time env variable
3. Run `flutter build apk --release`
4. Test APK on smartboard
5. (Optional) Generate `--split-per-abi` APKs for smaller size

---

## Open Questions

> [!IMPORTANT]
> **Q1: Where will the server run?**
> The FastAPI server needs to be reachable from the smartboard's IP.
> - **Option A**: Your existing PC on the same WiFi network as the smartboard
> - **Option B**: A Raspberry Pi dedicated server in the classroom
> - **Option C**: Cloud VPS (DigitalOcean/AWS) — needs internet, but works anywhere
>
> This affects the `BASE_URL` constant in the Flutter app.

> [!IMPORTANT]
> **Q2: Should the Streamlit app keep running alongside FastAPI?**
> You can run both in parallel — Streamlit on port 8501, FastAPI on port 8000.
> No conflict. This way teachers who prefer the web UI can still use Streamlit
> while the APK uses FastAPI.

> [!NOTE]
> **Q3: Smartboard camera resolution?**
> High resolution frames (e.g. 4K) sent over WiFi every 2 seconds could be
> slow. We can add a compression step in Flutter to resize to 1280×720 before
> sending. This has negligible impact on face detection accuracy.

---

## Effort Summary

| Phase | Task | Time |
|-------|------|------|
| 1 | FastAPI backend (all endpoints) | ~1 week |
| 2 | Flutter app foundation + auth | ~1 week |
| 3 | Teacher portal screens | ~1 week |
| 4 | Student + Admin screens | ~1 week |
| 5 | APK build + testing | ~3 days |
| **Total** | | **~5 weeks** |

> [!TIP]
> We can deliver a **working partial APK** faster — e.g., in 2 weeks — with
> just Login + Live Scan + Attendance Log. The remaining screens can be added
> iteratively. Want me to start with that minimal viable version?
