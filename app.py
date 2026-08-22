"""
app.py — EngageLens Phase 10 Entry Point
==========================================
Thin router:
  1. Init MongoDB + InsightFace (cached, same as before).
  2. Start Telegram linker thread.
  3. If not authenticated → show login page → st.stop().
  4. Check session timeout.
  5. Build st.navigation() with ONLY that role's page set.
  6. Run the selected page via nav.run().

Security: st.navigation() built from ROLE_PAGE_MAP means a student's
navigation object literally never contains teacher/admin page objects.
Defense-in-depth role guards inside each portal page provide a second layer.
"""

import streamlit as st

# ── Page config — set ONCE here, removed from all portal page files ────────────
st.set_page_config(
    page_title="EngageLens",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── MongoDB connectivity check ─────────────────────────────────────────────────
@st.cache_resource(show_spinner="Connecting to MongoDB…")
def _init_db():
    from database.mongo_client import get_db, MongoConnectionError
    try:
        return get_db(), None
    except MongoConnectionError as exc:
        return None, str(exc)

db, db_error = _init_db()

if db_error:
    st.error(f"**MongoDB not reachable.**\n{db_error}", icon="🔴")
    st.info(
        "**To start MongoDB:**\n"
        "```bash\nsudo systemctl start mongod\n```",
    )
    st.stop()

# ── Telegram Linker Thread ─────────────────────────────────────────────────────
try:
    from notifications.telegram_linker import start_linker_thread
    start_linker_thread()
except Exception as _tg_exc:
    import logging as _logging
    _logging.getLogger(__name__).warning("Could not start Telegram linker: %s", _tg_exc)

# ── InsightFace warm-up ────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading InsightFace models (buffalo_l)…")
def _init_detector():
    from face_recognition_module.detector import load_detector
    try:
        return load_detector(), None
    except RuntimeError as exc:
        return None, str(exc)

face_app, face_error = _init_detector()

if face_error:
    st.error(f"**InsightFace failed to load.**\n{face_error}", icon="⚠️")
    st.stop()

# ── Auth check ────────────────────────────────────────────────────────────────
from auth.auth_manager import is_authenticated, check_session_timeout

if not is_authenticated():
    from login import render_login_page
    render_login_page()
    st.stop()

# Session timeout check (auto-logout if idle)
check_session_timeout()

# Global CSS — Minimalistic editorial design (black & white, Outfit font)
_GLOBAL_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>

/* ── Design tokens ───────────────────────────────────────────────── */
:root {
    --bg:           #FAFAFA;
    --bg2:          #F3F3F1;
    --bg3:          #EBEBEA;
    --card:         #FFFFFF;
    --dark:         #1A1A1A;
    --muted:        #6B6B6B;
    --subtle:       #A0A09E;
    --border:       #E8E8E6;
    --border2:      rgba(26,26,26,0.06);
    --focus-ring:   rgba(26,26,26,0.10);
    --success:      #2D6A4F;
    --warn:         #92400E;
    --danger:       #991B1B;
    --info:         #1D4ED8;
    --r-sm:         8px;
    --r-md:         12px;
    --r-lg:         18px;
    --r-xl:         24px;
    --r-pill:       999px;
    --sh-sm:        0 1px 4px rgba(0,0,0,0.06);
    --sh-md:        0 4px 16px rgba(0,0,0,0.08);
    --sh-lg:        0 8px 32px rgba(0,0,0,0.10);
    /* Legacy aliases used in portal pages */
    --bg-card:      #FFFFFF;
    --border-color: #E8E8E6;
    --shadow-sm:    0 1px 4px rgba(0,0,0,0.06);
    --shadow-md:    0 4px 16px rgba(0,0,0,0.08);
    --radius-md:    12px;
}

/* ── Global fonts & base ─────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--dark) !important;
    -webkit-font-smoothing: antialiased;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CECECE; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #A0A09E; }

/* ── App background ──────────────────────────────────────────────── */
.stApp {
    background: var(--bg) !important;
}

.block-container {
    padding: 2rem 2.5rem 3rem 2.5rem !important;
    max-width: 1400px !important;
}

/* ── Hide toolbar & decoration ───────────────────────────────────── */
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: none !important;
}

[data-testid="stSidebarNav"] a {
    border-radius: var(--r-sm) !important;
    margin: 1px 6px !important;
    padding: 9px 12px !important;
    color: var(--muted) !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.01em !important;
    transition: all 0.15s ease !important;
    text-decoration: none !important;
    display: block !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: var(--bg2) !important;
    color: var(--dark) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: var(--bg2) !important;
    color: var(--dark) !important;
    font-weight: 700 !important;
    border-left: 2px solid var(--dark) !important;
}

/* ── Headings ────────────────────────────────────────────────────── */
h1 {
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.035em !important;
    color: var(--dark) !important;
    -webkit-text-fill-color: var(--dark) !important;
    background: none !important;
    line-height: 1.1 !important;
    margin-bottom: 0.2rem !important;
}
h2 {
    font-weight: 700 !important;
    font-size: 1.35rem !important;
    letter-spacing: -0.025em !important;
    color: var(--dark) !important;
}
h3 {
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    letter-spacing: -0.015em !important;
    color: var(--dark) !important;
}

/* ── Metric cards ────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    padding: 20px 24px !important;
    box-shadow: var(--sh-sm) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: var(--sh-md) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.70rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.10em !important;
    color: var(--subtle) !important;
}
[data-testid="stMetricValue"] {
    font-size: 2.2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
    color: var(--dark) !important;
    line-height: 1.1 !important;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: var(--dark) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: var(--r-pill) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 10px 28px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
    letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background: #333333 !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--sh-md) !important;
}

.stButton > button[kind="secondary"],
.stFormSubmitButton > button[kind="secondary"] {
    background: var(--card) !important;
    color: var(--dark) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-pill) !important;
    font-weight: 500 !important;
    font-family: 'Outfit', sans-serif !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="secondary"]:hover {
    background: var(--bg2) !important;
    border-color: var(--dark) !important;
}
.stButton > button {
    border-radius: var(--r-pill) !important;
    font-family: 'Outfit', sans-serif !important;
    transition: all 0.15s ease !important;
}

/* ── Tabs ────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    border-radius: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
    border: none !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 0 !important;
    color: var(--muted) !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 10px 20px 10px 0 !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.15s ease !important;
    margin-right: 20px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: var(--dark) !important;
    background: transparent !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--dark) !important;
    font-weight: 700 !important;
    border-bottom-color: var(--dark) !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* ── Inputs ──────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stSelectbox > div > div > div,
.stMultiSelect > div > div,
.stDateInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    color: var(--dark) !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.875rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {
    color: var(--subtle) !important;
    opacity: 1 !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--dark) !important;
    box-shadow: 0 0 0 2px var(--focus-ring) !important;
    outline: none !important;
}

/* ── Form field labels ───────────────────────────────────────────── */
.stTextInput label, .stSelectbox label, .stDateInput label,
.stNumberInput label, .stTextArea label, .stSlider label,
.stMultiSelect label, .stRadio label, .stRadio > div > label {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    color: var(--subtle) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
}

/* ── Border wrapper blocks ───────────────────────────────────────── */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--sh-sm) !important;
    transition: box-shadow 0.15s ease !important;
}
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--sh-md) !important;
}

/* ── Alerts ──────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--r-md) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    border: none !important;
}

/* ── DataFrames ──────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--r-lg) !important;
    overflow: hidden !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--sh-sm) !important;
}

/* ── Expander ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
}

/* ── File uploader ───────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: var(--bg2) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--r-lg) !important;
    transition: border-color 0.15s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--dark) !important;
}

/* ── Progress bar ────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: var(--bg3) !important;
    border-radius: var(--r-pill) !important;
    height: 6px !important;
}
[data-testid="stProgress"] > div > div > div {
    background: var(--dark) !important;
    border-radius: var(--r-pill) !important;
}

/* ── Dividers ────────────────────────────────────────────────────── */
hr {
    border-color: var(--border) !important;
    margin: 1.25rem 0 !important;
}

/* ── Captions ────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--subtle) !important;
    font-size: 0.76rem !important;
}

/* ── Radio ───────────────────────────────────────────────────────── */
[data-testid="stRadio"] label {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
}

/* ── Custom component classes ────────────────────────────────────── */
.card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 24px;
    box-shadow: var(--sh-sm);
    margin-bottom: 12px;
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.card:hover { box-shadow: var(--sh-md); transform: translateY(-2px); }

.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: var(--r-pill);
    font-size: 0.70rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-accent  { background: #F0F0EF; color: var(--dark);  border: 1px solid var(--border); }
.badge-success { background: #ECFDF5; color: #065F46;      border: 1px solid #A7F3D0; }
.badge-warning { background: #FFFBEB; color: #92400E;      border: 1px solid #FDE68A; }
.badge-danger  { background: #FEF2F2; color: #991B1B;      border: 1px solid #FECACA; }
.badge-info    { background: #EFF6FF; color: #1D4ED8;      border: 1px solid #BFDBFE; }

.section-chip {
    display: inline-block;
    background: var(--bg2);
    color: var(--dark);
    border: 1px solid var(--border);
    padding: 2px 10px;
    border-radius: var(--r-pill);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    margin: 2px;
}

.user-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 18px 16px;
    margin-bottom: 12px;
    text-align: center;
}
.user-card .avatar { font-size: 1.8rem; margin-bottom: 6px; }
.user-card .uname  { font-weight: 700; font-size: 0.95rem; letter-spacing: -0.01em; color: var(--dark); }
.user-card .urole  { font-size: 0.68rem; color: var(--subtle); text-transform: uppercase; letter-spacing: 0.10em; margin-top: 2px; }

.override-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px;
    box-shadow: var(--sh-sm);
    margin-bottom: 16px;
}

.stat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 18px 20px;
    box-shadow: var(--sh-sm);
    text-align: center;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--sh-md); }
.stat-number { font-size: 2.4rem; font-weight: 800; letter-spacing: -0.04em; color: var(--dark); }
.stat-label  { font-size: 0.70rem; color: var(--subtle); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }
.present-num { color: var(--dark); }
.absent-num  { color: var(--muted); }
.total-num   { color: var(--subtle); }

.warn-banner {
    background: #FEF9EC;
    border-left: 3px solid #D97706;
    border-radius: var(--r-sm);
    padding: 14px 18px;
    margin: 14px 0;
    color: var(--warn);
    font-size: 0.875rem;
}

.gradient-divider {
    height: 1px;
    background: var(--border);
    margin: 16px 0;
}

.profile-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 24px;
    box-shadow: var(--sh-sm);
}
.field-label { font-size: 0.70rem; color: var(--subtle); text-transform: uppercase; letter-spacing: 0.09em; }
.field-value { font-size: 1.05rem; font-weight: 600; color: var(--dark); margin-bottom: 16px; }

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
.fade-in { animation: fadeInUp 0.4s ease forwards; }

@keyframes pulse-ring {
    0%   { box-shadow: 0 0 0 0 rgba(26,26,26,0.3); }
    70%  { box-shadow: 0 0 0 10px rgba(26,26,26,0); }
    100% { box-shadow: 0 0 0 0 rgba(26,26,26,0); }
}
.pulse { animation: pulse-ring 2.5s infinite; }

</style>
"""

st.html(_GLOBAL_CSS)

# Sidebar: user info + logout ────────────────────────────────────────────────
role      = st.session_state.get("role", "")
full_name = st.session_state.get("full_name", "User")

ROLE_ICONS = {"student": "🧑‍🎓", "teacher": "👩‍🏫", "admin": "🛠️"}

with st.sidebar:
    # Premium user card
    st.html(
        f'<div class="user-card fade-in">'
        f'<div class="avatar">{ROLE_ICONS.get(role, "👤")}</div>'
        f'<div class="uname">{full_name}</div>'
        f'<div class="urole">{role}</div>'
        f'</div>'
    )

    if st.button("🚪 Logout", use_container_width=True, key="sidebar_logout_btn"):
        from auth.auth_manager import logout
        logout()

    st.divider()

    # Quick stats
    try:
        from database.db_operations import get_attendance_stats
        stats = get_attendance_stats()
        c1, c2 = st.columns(2)
        c1.metric("Students", stats["total_students"])
        c2.metric("Records", stats["total_records"])
    except Exception:
        pass


# ── Role → Page Map ────────────────────────────────────────────────────────────
ROLE_PAGE_MAP: dict[str, list] = {
    "student": [
        st.Page(
            "portals/student_portal/dashboard.py",
            title="My Dashboard",
            icon="🏠",
            default=True,
        ),
        st.Page(
            "portals/student_portal/history.py",
            title="My Attendance",
            icon="📅",
        ),
        st.Page(
            "portals/student_portal/profile.py",
            title="My Profile",
            icon="👤",
        ),
    ],
    "teacher": [
        st.Page(
            "portals/teacher_portal/class_overview.py",
            title="Class Overview",
            icon="📋",
            default=True,
        ),
        st.Page(
            "portals/teacher_portal/override.py",
            title="Override Attendance",
            icon="✏️",
        ),
        st.Page(
            "portals/teacher_portal/scan.py",
            title="Batch Scan",
            icon="📸",
        ),
        st.Page(
            "portals/teacher_portal/live_scan.py",
            title="Live Scan",
            icon="🎥",
        ),
        st.Page(
            "portals/teacher_portal/enroll.py",
            title="Enroll Student",
            icon="🧑‍🎓",
        ),
        st.Page(
            "portals/teacher_portal/alerts.py",
            title="Absentee Alerts",
            icon="📢",
        ),
    ],
    "admin": [
        st.Page(
            "portals/admin_portal/user_management.py",
            title="User Management",
            icon="👥",
            default=True,
        ),
        st.Page(
            "portals/admin_portal/class_management.py",
            title="Class Management",
            icon="🏫",
        ),
        st.Page(
            "portals/admin_portal/system_config.py",
            title="System Config",
            icon="⚙️",
        ),
        st.Page(
            "portals/admin_portal/system_health.py",
            title="System Health",
            icon="🩺",
        ),
        st.Page(
            "portals/admin_portal/audit_viewer.py",
            title="Audit Log",
            icon="🔍",
        ),
    ],

}

pages = ROLE_PAGE_MAP.get(role, [])
if not pages:
    st.error(f"No pages configured for role '{role}'. Contact admin.", icon="🚫")
    st.stop()

nav = st.navigation(pages)
nav.run()
