"""
portals/admin_portal/system_health.py
=======================================
Admin — System Health Dashboard (Phase 10).

Shows:
  - MongoDB collection counts and storage size
  - InsightFace/ONNX model load status
  - Telegram bot connectivity check
  - Last 24h notification success/failure rate chart
  - Enrolled student photo storage size
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from auth.auth_manager import require_role, check_session_timeout, update_last_activity, get_current_user

check_session_timeout()
require_role("admin")
update_last_activity()

st.markdown("""
<style>
.admin-badge {
    background: var(--bg2);
    border: 1px solid var(--border);
    color: var(--dark);
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 10px;
}
.health-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 16px;
    margin-bottom: 12px;
}
.status-ok  { color: #2D6A4F; font-weight: 600; }
.status-err { color: #991B1B; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

user = get_current_user()
from database.mongo_client import get_db
import config

db = get_db()

st.markdown('<div class="admin-badge">🛠️ ADMIN PORTAL</div>', unsafe_allow_html=True)
st.title("🩺 System Health")
st.caption(f"Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

if st.button("🔄 Refresh", key="health_refresh"):
    st.rerun()

st.divider()

# ── MongoDB Collection Stats ───────────────────────────────────────────────────
st.markdown("### 🗄️ MongoDB Collections")

collections = ["students", "attendance", "users", "audit_log", "notifications_log", "system_config"]
col_data = []
for cname in collections:
    try:
        count = db[cname].count_documents({})
        stats = db.command("collstats", cname)
        size_kb = round(stats.get("size", 0) / 1024, 1)
        col_data.append({
            "Collection":   cname,
            "Documents":    count,
            "Size (KB)":    size_kb,
            "Indexes":      len(stats.get("indexSizes", {})),
        })
    except Exception as exc:
        col_data.append({
            "Collection": cname,
            "Documents": "?",
            "Size (KB)": "?",
            "Indexes": "?",
        })

col_df = pd.DataFrame(col_data)
st.dataframe(col_df, use_container_width=True, hide_index=True)

# Quick metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Users", db["users"].count_documents({}))
c2.metric("🧑‍🎓 Students", db["students"].count_documents({}))
c3.metric("📋 Attendance Records", db["attendance"].count_documents({}))
c4.metric("🔍 Audit Log Entries", db["audit_log"].count_documents({}))

st.divider()

# ── InsightFace / ONNX Status ──────────────────────────────────────────────────
st.markdown("### 🤖 AI Model Status")
col_m1, col_m2 = st.columns(2)

with col_m1:
    try:
        from face_recognition_module.detector import load_detector
        fa = load_detector()
        st.markdown('<span class="status-ok">✅ InsightFace (buffalo_l) — LOADED</span>', unsafe_allow_html=True)
        st.caption(f"Model: {config.INSIGHTFACE_MODEL} | Context: {'CPU' if config.CTX_ID == -1 else f'GPU:{config.CTX_ID}'}")
    except Exception as exc:
        st.markdown(f'<span class="status-err">❌ InsightFace — FAILED: {exc}</span>', unsafe_allow_html=True)

with col_m2:
    try:
        import onnxruntime as ort
        st.markdown('<span class="status-ok">✅ ONNX Runtime — AVAILABLE</span>', unsafe_allow_html=True)
        st.caption(f"Version: {ort.__version__} | Providers: {ort.get_available_providers()}")
    except ImportError:
        st.markdown('<span class="status-err">❌ ONNX Runtime — NOT INSTALLED</span>', unsafe_allow_html=True)

st.divider()

# ── Telegram Bot Status ───────────────────────────────────────────────────────
st.markdown("### 📡 Telegram Bot Status")
bot_token = config.TELEGRAM_BOT_TOKEN

if not bot_token:
    st.markdown('<span class="status-err">❌ TELEGRAM_BOT_TOKEN not set in .env</span>', unsafe_allow_html=True)
else:
    try:
        import requests
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=5,
        )
        if resp.ok and resp.json().get("ok"):
            bot_info = resp.json()["result"]
            st.markdown(
                f'<span class="status-ok">✅ Bot connected: @{bot_info["username"]} ({bot_info["first_name"]})</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="status-err">❌ Bot API returned error: {resp.text[:100]}</span>',
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.markdown(
            f'<span class="status-err">❌ Telegram unreachable: {exc}</span>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Notification Success Rate (last 24h) ──────────────────────────────────────
st.markdown("### 📨 Notification Success Rate (last 24h)")

since = datetime.utcnow() - timedelta(hours=24)
notif_records = list(db["notifications_log"].find(
    {"sent_at": {"$gte": since}},
    {"_id": 0, "status": 1},
))

if not notif_records:
    st.info("No notification attempts in the last 24 hours.", icon="📭")
else:
    from collections import Counter
    counts = Counter(r.get("status", "unknown") for r in notif_records)
    total = len(notif_records)
    sent    = counts.get("sent", 0)
    failed  = counts.get("failed", 0)
    skipped = counts.get("skipped_no_chat_id", 0)

    c_s, c_f, c_sk, c_t = st.columns(4)
    c_s.metric("✅ Sent",    sent)
    c_f.metric("❌ Failed",  failed)
    c_sk.metric("⚠️ Skipped", skipped)
    c_t.metric("Total",     total)

    fig = go.Figure(go.Pie(
        values=[sent, failed, skipped],
        labels=["Sent", "Failed", "No parent linked"],
        marker_colors=["#1A1A1A", "#E5E5E3", "#A0A09E"],
        hole=0.5,
    ))
    fig.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#6B6B6B", family="Outfit"),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Enrolled Photos Storage ───────────────────────────────────────────────────
st.markdown("### 📁 Enrolled Faces Storage")
import shutil
enrolled_dir = config.ENROLLED_FACES_DIR
if enrolled_dir.exists():
    total_bytes = sum(f.stat().st_size for f in enrolled_dir.rglob("*") if f.is_file())
    num_dirs    = sum(1 for d in enrolled_dir.iterdir() if d.is_dir())
    num_photos  = sum(1 for f in enrolled_dir.rglob("*") if f.is_file() and not f.name.startswith("."))
    st.markdown(f"📂 `{enrolled_dir}` — **{num_dirs}** students · **{num_photos}** photos · **{total_bytes/1024:.1f} KB**")
else:
    st.warning("Enrolled faces directory not found.", icon="⚠️")

st.caption(f"EngageLens v2.0 · Admin Portal · {user.get('full_name','')}")
