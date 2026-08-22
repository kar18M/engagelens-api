"""
login.py — EngageLens Phase 10 login entry point.
Softly warm-pastel theme. Clean, tactile, intentionally soft.
"""

import streamlit as st
from auth.auth_manager import login


# ── Minimalistic editorial login theme ────────────────────────────────────────
_LOGIN_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
[data-testid="stSidebar"]    { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

html, body, [class*="css"] {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #1A1A1A !important;
    -webkit-font-smoothing: antialiased;
}

.stApp {
    background: #FAFAFA !important;
}

/* ── Subtle background grid pattern ─────────────────────────────── */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    opacity: 0.035;
    background-image:
        linear-gradient(#1A1A1A 1px, transparent 1px),
        linear-gradient(90deg, #1A1A1A 1px, transparent 1px);
    background-size: 40px 40px;
}

/* ── Login card ──────────────────────────────────────────────────── */
.login-card {
    background: #FFFFFF;
    border: 1px solid #E8E8E6;
    border-radius: 20px;
    padding: 48px 44px 40px 44px;
    box-shadow: 0 2px 24px rgba(0,0,0,0.06);
    animation: cardIn 0.4s cubic-bezier(.22,.68,0,1.1) forwards;
    margin-top: 40px;
}

@keyframes cardIn {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Logo mark ───────────────────────────────────────────────────── */
.login-logomark {
    width: 48px;
    height: 48px;
    background: #1A1A1A;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px auto;
    font-size: 1.4rem;
    animation: popIn 0.45s cubic-bezier(.22,.68,0,1.4) 0.05s both;
}

@keyframes popIn {
    from { opacity: 0; transform: scale(0.6); }
    to   { opacity: 1; transform: scale(1); }
}

.login-title {
    text-align: center;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: #1A1A1A;
    margin-bottom: 6px;
    line-height: 1.05;
}

.login-subtitle {
    text-align: center;
    color: #A0A09E;
    font-size: 0.85rem;
    font-weight: 400;
    margin-bottom: 28px;
    letter-spacing: 0.01em;
}

/* ── Role indicator row ──────────────────────────────────────────── */
.role-row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-bottom: 28px;
    padding-bottom: 24px;
    border-bottom: 1px solid #E8E8E6;
}

.role-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
}
.role-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #E8E8E6;
}
.role-dot-dark { background: #1A1A1A; }
.role-text {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #A0A09E;
}

/* ── Inputs ──────────────────────────────────────────────────────── */
.stTextInput > div > div > input {
    background: #F8F8F7 !important;
    border: 1px solid #E8E8E6 !important;
    border-radius: 10px !important;
    color: #1A1A1A !important;
    font-size: 0.9rem !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 11px 16px !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input::placeholder {
    color: #B0B0AE !important;
    opacity: 1 !important;
}
.stTextInput > div > div > input:focus {
    border-color: #1A1A1A !important;
    box-shadow: 0 0 0 2px rgba(26,26,26,0.08) !important;
    outline: none !important;
    background: #FFFFFF !important;
}

.stTextInput label {
    font-size: 0.70rem !important;
    font-weight: 600 !important;
    color: #A0A09E !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
}
.stTextInput > div {
    border: none !important;
    background: transparent !important;
}

/* ── Submit button ───────────────────────────────────────────────── */
.stFormSubmitButton > button {
    background: #1A1A1A !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    font-family: 'Outfit', sans-serif !important;
    padding: 12px 24px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
    letter-spacing: 0.01em !important;
    margin-top: 10px !important;
}
.stFormSubmitButton > button:hover {
    background: #333333 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(26,26,26,0.18) !important;
}

/* ── Footer ──────────────────────────────────────────────────────── */
.login-footer {
    text-align: center;
    margin-top: 24px;
    color: #B0B0AE;
    font-size: 0.70rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CECECE; border-radius: 99px; }
</style>
"""

_LOGIN_CARD_HTML = """
<div class="login-card">
  <div class="login-logomark">🎓</div>
  <div class="login-title">EngageLens</div>
  <div class="login-subtitle">AI-Powered Classroom Attendance System</div>
  <div class="role-row">
    <div class="role-item">
      <div class="role-dot role-dot-dark"></div>
      <div class="role-text">Student</div>
    </div>
    <div class="role-item">
      <div class="role-dot role-dot-dark"></div>
      <div class="role-text">Teacher</div>
    </div>
    <div class="role-item">
      <div class="role-dot role-dot-dark"></div>
      <div class="role-text">Admin</div>
    </div>
  </div>
</div>
"""


def render_login_page():
    """Render the full login UI."""

    st.html(_LOGIN_CSS)

    if st.session_state.get("timeout_triggered"):
        st.warning(
            "⏱️ Your session timed out due to inactivity. Please log in again.",
            icon="⏱️",
        )
        st.session_state.pop("timeout_triggered", None)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.html(_LOGIN_CARD_HTML)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username_input",
                autocomplete="username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password_input",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "🔑  Sign In",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.", icon="❌")
            else:
                with st.spinner("Verifying credentials…"):
                    success, error_msg = login(username, password)

                if success:
                    st.success(
                        f"Welcome back, **{st.session_state.get('full_name', username)}**!  "
                        "Redirecting…",
                        icon="✅",
                    )
                    st.rerun()
                else:
                    st.error(error_msg, icon="🔴")

        st.html(
            "<div class='login-footer'>"
            "EngageLens v2.0 &nbsp;·&nbsp; Phase 10 &nbsp;·&nbsp; Powered by InsightFace + MongoDB"
            "</div>"
        )
