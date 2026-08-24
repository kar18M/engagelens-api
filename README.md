---
title: EngageLens API
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: true
---

# EngageLens API

FastAPI backend for the **EngageLens** smart attendance system.

- Face recognition via **InsightFace** (RetinaFace + ArcFace, buffalo_l)
- Cloud database: **Supabase** (PostgreSQL)
- REST API consumed by the **Flutter Android APK**

## API Docs

Visit `https://<your-space>.hf.space/docs` for the interactive Swagger UI.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login → JWT token |
| GET | `/students` | List all students |
| POST | `/recognize` | Send image → get recognized names |
| POST | `/attendance/mark` | Mark student present |
| GET | `/attendance` | Get attendance log |
| POST | `/enroll` | Enroll new student face |

## Environment Variables (set as Secrets in HF Spaces)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `DB_BACKEND` | Set to `supabase` |
