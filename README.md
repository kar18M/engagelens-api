# EngageLens — Classroom Attendance System
## Robust Multi-Face Recognition · InsightFace (RetinaFace + ArcFace) · MongoDB

EngageLens detects and recognises every student in a high-resolution classroom
photo simultaneously — including turned heads, side profiles, and small/distant
faces at the back of the room.  It runs entirely locally with no cloud APIs.

---

## Tech Stack

| Component | Library |
|---|---|
| Face Detection | InsightFace `buffalo_l` → **RetinaFace** |
| Face Embeddings | InsightFace `buffalo_l` → **ArcFace** (512-d) |
| Database | **MongoDB** (local, `engagelens` DB) |
| Frontend | **Streamlit** multi-page app |
| Live Mode | **streamlit-webrtc** |
| Charts | **Plotly** |
| Image I/O | **OpenCV** |

---

## Prerequisites

### 1. Python 3.10+

```bash
python3 --version   # should be 3.10 or higher
```

### 2. MongoDB (local instance)

**Ubuntu/Debian:**
```bash
# Install
sudo apt install -y mongodb

# Start the service
sudo systemctl start mongod
sudo systemctl enable mongod   # auto-start on boot

# Verify it's running
mongosh --eval "db.adminCommand('ping')"
```

**Manual install (alternative):**
```bash
mongod --dbpath /data/db --fork --logpath /var/log/mongod.log
```

MongoDB must be running at `mongodb://localhost:27017/` before starting EngageLens.

---

## Installation

### Step 1 — Clone / enter project directory

```bash
cd /home/karthick/smart-attend-modify
```

### Step 2 — Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note on InsightFace / onnxruntime:**
> If `onnxruntime` fails to build on your architecture, try:
> ```bash
> pip install onnxruntime-openvino   # Intel CPUs
> # or
> pip install onnxruntime-gpu        # NVIDIA GPU
> ```

### Step 4 — First-run model download (internet required once)

On the first run, InsightFace will automatically download the **buffalo_l** model
pack (~500 MB) from the InsightFace CDN to `~/.insightface/models/buffalo_l/`.

This only happens once.  Subsequent runs use the cached local copy.

---

## Running EngageLens

```bash
# Make sure MongoDB is running first
sudo systemctl start mongod

# Activate venv if not already
source venv/bin/activate

# Launch the app
streamlit run app.py
```

Open your browser at **http://localhost:8501**

---

## Workflow

### 1. Enroll Students (Page 4 — 🧑‍🎓 Enroll Student)

Multi-angle enrollment is **mandatory** for robust classroom recognition.
When a student turns their head in a classroom photo, a single front-only
embedding may fail to match.  Storing front + left + right profile embeddings
lets the recognizer match regardless of head pose.

**Steps:**
1. Open the **Enroll Student** page.
2. Enter the student's ID (e.g. `CS101`) and full name.
3. Upload **Front-facing photo** (required).
4. Upload **Left profile photo** (recommended — student looking ~45° left).
5. Upload **Right profile photo** (recommended — student looking ~45° right).
6. Live validation confirms a single face was detected in each photo.
7. Click **Enroll Student**.

Repeat for all students in the class.

### 2. Batch Classroom Scan (Page 2 — 📸 Batch Classroom Scan)

**Primary path for 50–60 student classrooms.**

1. Open the **Batch Classroom Scan** page.
2. Upload a high-resolution classroom photo (JPEG/PNG, ≥ 2 MP recommended).
3. The system:
   - Splits the image into overlapping 640×640 tiles.
   - Runs RetinaFace detection on each tile at full resolution.
   - Remaps bounding boxes to full-image coordinates.
   - Deduplicates overlapping detections via IoU NMS.
   - Matches each face against all stored angle-embeddings.
4. Annotated image appears with name / matched angle / distance on each face.
5. Review the **X detected / Y recognised / Z unknown** counts.
6. Click **Commit Attendance** to write records to MongoDB.

### 3. Live Attendance (Page 1 — 🎥 Live Attendance)

For small groups (study rooms, seminars — **not** full classrooms).

1. Open the **Live Attendance** page.
2. Click **Start** to begin the webcam stream.
3. Every 3rd frame is processed for face detection + recognition.
4. Attendance is marked automatically for each recognised student.
5. Today's log updates in real time in the right panel.

### 4. Attendance Log (Page 3 — 📋 Attendance Log)

- Pick any date to view that day's attendance table.
- Columns include **Matched Angle** and **Distance** for recognition quality auditing.
- Download the table as CSV.
- Trend chart shows daily attendance counts over time.

---

## MongoDB Collections

### `engagelens.students`

```json
{
  "student_id": "CS101",
  "name": "Jane Doe",
  "face_encodings": [
    {"angle": "front",        "embedding": [...512 floats], "photo_path": "..."},
    {"angle": "left_profile", "embedding": [...512 floats], "photo_path": "..."},
    {"angle": "right_profile","embedding": [...512 floats], "photo_path": "..."}
  ],
  "enrolled_on": "ISODate"
}
```

### `engagelens.attendance`

```json
{
  "student_id": "CS101",
  "name": "Jane Doe",
  "date": "2026-07-28",
  "timestamp": "ISODate",
  "status": "Present",
  "matched_angle": "left_profile",
  "match_distance": 0.3142
}
```

---

## Tuning Recognition Accuracy

| Parameter | Location | Default | Notes |
|---|---|---|---|
| `RECOGNITION_THRESHOLD` | `config.py` | `0.45` | Lower = stricter. Tune if too many false positives or unknowns. |
| `MIN_FACE_SIZE_PX` | `config.py` | `20` | Increase if tiny false-positive detections appear. |
| `TILE_SIZE` | `config.py` | `640` | Larger tiles = more context, slower. |
| `TILE_OVERLAP` | `config.py` | `80` | Increase if faces at tile edges are missed. |

---

## Fallback If InsightFace Fails to Install

1. **YOLOv8-face + deepface ArcFace**
   ```bash
   pip install ultralytics deepface
   ```
   Update `detector.py` to use `YOLO("yolov8n-face.pt")` for detection
   and `DeepFace.represent(..., model_name="ArcFace")` for embeddings.

2. **Classic face_recognition (dlib)** — last resort
   ```bash
   pip install face-recognition
   ```
   Note: Multi-angle and small-face recall will be noticeably worse.
   Dlib's HOG/CNN detector was tuned for single near-frontal faces.

---

## Project Structure

```
smart-attend-modify/
├── app.py                          # Main entrypoint
├── config.py                       # All tunable constants
├── requirements.txt
├── README.md
├── batch_processor.py              # Tiling → detect → NMS → recognise
├── video_processor.py              # WebRTC live mode (small groups)
├── database/
│   ├── mongo_client.py             # Connection factory + index setup
│   └── db_operations.py           # All CRUD operations
├── face_recognition_module/
│   ├── detector.py                 # InsightFace FaceAnalysis wrapper
│   ├── enroll.py                   # Multi-angle enrollment logic
│   ├── recognizer.py               # Multi-angle recognition engine
│   └── encodings_store.py         # Gallery loader, cosine distance
├── pages/
│   ├── 1_Live_Attendance.py
│   ├── 2_Batch_Classroom_Scan.py
│   ├── 3_Attendance_Log.py
│   └── 4_Enroll_Student.py
└── data/
    └── enrolled_faces/             # Per-student enrollment photos (runtime)
```

---

## License

MIT License — free for educational and research use.
