import streamlit as st

st.set_page_config(
    page_title="Cyber Tech Login",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------
# Session state
# -------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# -------------------------------
# Custom CSS
# -------------------------------
st.markdown("""
<style>
/* ===== Hide Streamlit default ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}

/* ===== Main app background ===== */
.stApp {
    background:
        radial-gradient(circle at 20% 20%, rgba(0,255,255,0.14), transparent 25%),
        radial-gradient(circle at 80% 30%, rgba(138,43,226,0.18), transparent 28%),
        radial-gradient(circle at 50% 80%, rgba(0,128,255,0.14), transparent 25%),
        linear-gradient(135deg, #050816 0%, #081125 35%, #0a0f1f 65%, #040712 100%);
    color: white;
    overflow: hidden;
}

/* ===== Animated background layer ===== */
.cyber-bg {
    position: fixed;
    inset: 0;
    z-index: -10;
    overflow: hidden;
    pointer-events: none;
}

/* moving glow blobs */
.cyber-bg::before,
.cyber-bg::after {
    content: "";
    position: absolute;
    width: 45vw;
    height: 45vw;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.22;
    animation: floatGlow 12s ease-in-out infinite alternate;
}

.cyber-bg::before {
    top: -10%;
    left: -10%;
    background: #00e5ff;
}

.cyber-bg::after {
    bottom: -15%;
    right: -10%;
    background: #8a2be2;
    animation-duration: 15s;
}

@keyframes floatGlow {
    0%   {transform: translate(0, 0) scale(1);}
    50%  {transform: translate(60px, 30px) scale(1.1);}
    100% {transform: translate(-40px, -20px) scale(0.95);}
}

/* grid overlay */
.grid-overlay {
    position: fixed;
    inset: 0;
    z-index: -9;
    background-image:
        linear-gradient(rgba(0,255,255,0.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,255,0.08) 1px, transparent 1px);
    background-size: 38px 38px;
    mask-image: linear-gradient(to bottom, rgba(255,255,255,0.9), rgba(255,255,255,0.15));
    animation: moveGrid 16s linear infinite;
    pointer-events: none;
}

@keyframes moveGrid {
    from {transform: translateY(0px);}
    to   {transform: translateY(38px);}
}

/* scan line */
.scanline {
    position: fixed;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, transparent, rgba(0,255,255,0.9), transparent);
    box-shadow: 0 0 20px rgba(0,255,255,0.85);
    z-index: -8;
    animation: scan 6s linear infinite;
    pointer-events: none;
}

@keyframes scan {
    0%   {top: 0%;}
    100% {top: 100%;}
}

/* ===== Main containers ===== */
.main-wrap {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 30px;
}

.hero-box {
    display: grid;
    grid-template-columns: 1.2fr 0.9fr;
    gap: 32px;
    width: 100%;
    max-width: 1200px;
    align-items: center;
}

/* ===== Left panel ===== */
.left-panel {
    padding: 30px 20px 30px 10px;
}

.logo-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 18px;
    border-radius: 999px;
    border: 1px solid rgba(0,255,255,0.25);
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(8px);
    color: #9cfaff;
    font-size: 14px;
    letter-spacing: 1px;
    box-shadow: 0 0 20px rgba(0,255,255,0.12);
    animation: pulseBadge 2.3s ease-in-out infinite;
}

@keyframes pulseBadge {
    0%, 100% {box-shadow: 0 0 20px rgba(0,255,255,0.08);}
    50%      {box-shadow: 0 0 30px rgba(0,255,255,0.25);}
}

.main-title {
    font-size: 64px;
    font-weight: 900;
    line-height: 1.0;
    margin-top: 26px;
    margin-bottom: 18px;
    color: #ffffff;
    text-shadow: 0 0 10px rgba(0,255,255,0.22);
}

.main-title span {
    color: #00e5ff;
    text-shadow: 0 0 12px rgba(0,229,255,0.65), 0 0 28px rgba(0,229,255,0.35);
}

.sub-title {
    font-size: 18px;
    color: #b7c9df;
    max-width: 680px;
    line-height: 1.7;
}

.feature-row {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 28px;
}

.feature-chip {
    padding: 12px 18px;
    border-radius: 14px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(0,255,255,0.18);
    color: #d7f8ff;
    backdrop-filter: blur(10px);
    transition: all 0.25s ease;
    box-shadow: 0 0 18px rgba(0,255,255,0.05);
}

.feature-chip:hover {
    transform: translateY(-4px) scale(1.02);
    border-color: rgba(0,255,255,0.45);
    box-shadow: 0 0 24px rgba(0,255,255,0.22);
}

/* ===== Login Card ===== */
.login-card {
    position: relative;
    border-radius: 28px;
    padding: 28px 26px 22px 26px;
    background: rgba(8, 18, 38, 0.58);
    border: 1px solid rgba(0,255,255,0.18);
    backdrop-filter: blur(16px);
    box-shadow:
        0 0 0 1px rgba(255,255,255,0.03) inset,
        0 0 28px rgba(0,255,255,0.10),
        0 0 80px rgba(138,43,226,0.10);
    overflow: hidden;
    animation: floatCard 5s ease-in-out infinite;
}

.login-card::before {
    content: "";
    position: absolute;
    inset: -1px;
    border-radius: 28px;
    padding: 1px;
    background: linear-gradient(135deg, rgba(0,229,255,0.8), rgba(138,43,226,0.6), rgba(0,229,255,0.6));
    -webkit-mask:
        linear-gradient(#fff 0 0) content-box,
        linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
            mask-composite: exclude;
    pointer-events: none;
    opacity: 0.65;
}

@keyframes floatCard {
    0%, 100% {transform: translateY(0px);}
    50%      {transform: translateY(-6px);}
}

.card-title {
    font-size: 30px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 6px;
    text-align: center;
}

.card-sub {
    font-size: 14px;
    color: #a9bdd8;
    text-align: center;
    margin-bottom: 14px;
}

.status-dot {
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #00ff99;
    box-shadow: 0 0 14px #00ff99;
    margin-right: 8px;
}

/* ===== Streamlit form ===== */
div[data-testid="stTextInput"] > div > div input {
    background: rgba(255,255,255,0.05) !important;
    color: #ffffff !important;
    border-radius: 16px !important;
    border: 1px solid rgba(0,255,255,0.18) !important;
    padding: 14px 16px !important;
    box-shadow: 0 0 0 rgba(0,0,0,0);
    transition: all 0.25s ease !important;
}

div[data-testid="stTextInput"] > div > div input:focus {
    border: 1px solid rgba(0,255,255,0.75) !important;
    box-shadow: 0 0 0 2px rgba(0,229,255,0.10), 0 0 18px rgba(0,229,255,0.30) !important;
}

/* label */
div[data-testid="stTextInput"] label p {
    color: #d7f8ff !important;
    font-weight: 600 !important;
}

/* button */
div.stButton > button {
    width: 100%;
    border: none;
    border-radius: 16px;
    padding: 0.9rem 1rem;
    font-size: 16px;
    font-weight: 800;
    color: #04111f;
    background: linear-gradient(90deg, #00e5ff, #5df5ff, #7b61ff);
    box-shadow: 0 0 20px rgba(0,229,255,0.35), 0 0 40px rgba(123,97,255,0.22);
    transition: all 0.25s ease;
    letter-spacing: 0.3px;
}

div.stButton > button:hover {
    transform: translateY(-3px) scale(1.015);
    box-shadow: 0 0 28px rgba(0,229,255,0.55), 0 0 58px rgba(123,97,255,0.30);
}

div.stButton > button:active {
    transform: scale(0.985);
    box-shadow: 0 0 16px rgba(0,229,255,0.45);
}

/* small links / helper text */
.helper-text {
    text-align: center;
    color: #8fa7c4;
    font-size: 13px;
    margin-top: 10px;
}

.helper-text span {
    color: #00e5ff;
    cursor: pointer;
}

.cyber-line {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,255,255,0.65), transparent);
    margin: 14px 0 18px 0;
    box-shadow: 0 0 10px rgba(0,255,255,0.35);
}

/* dashboard box */
.dashboard-box {
    border-radius: 24px;
    padding: 22px;
    background: rgba(8, 18, 38, 0.58);
    border: 1px solid rgba(0,255,255,0.18);
    backdrop-filter: blur(16px);
    box-shadow: 0 0 28px rgba(0,255,255,0.10);
    margin-top: 12px;
}

/* responsive */
@media (max-width: 980px) {
    .hero-box {
        grid-template-columns: 1fr;
    }
    .main-title {
        font-size: 44px;
    }
    .left-panel {
        padding: 0;
    }
}
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Background HTML
# -------------------------------
st.markdown("""
<div class="cyber-bg"></div>
<div class="grid-overlay"></div>
<div class="scanline"></div>
""", unsafe_allow_html=True)

# -------------------------------
# Login function
# -------------------------------
def check_login(user, password):
    # เปลี่ยนตรงนี้เป็น user/pass ที่คุณต้องการ
    valid_user = "admin"
    valid_pass = "1234"
    return user == valid_user and password == valid_pass

# -------------------------------
# LOGGED IN
# -------------------------------
if st.session_state.logged_in:
    st.markdown("""
    <div class="main-wrap">
        <div style="width:100%; max-width:1200px;">
            <div class="logo-badge">⚡ SYSTEM ONLINE</div>
            <div class="main-title" style="margin-top:20px;">Welcome back, <span>""" + st.session_state.username + """</span></div>
            <div class="sub-title">คุณเข้าสู่ระบบสำเร็จแล้ว หน้านี้คือ Dashboard ตัวอย่างสำหรับต่อยอดไปยังระบบตรวจคลิป AI ของคุณ</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="dashboard-box">
            <h3>📂 Upload Clips</h3>
            <p style="color:#b7c9df;">อัปโหลดไฟล์วิดีโอเพื่อเริ่มตรวจสอบ</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="dashboard-box">
            <h3>🤖 AI Analysis</h3>
            <p style="color:#b7c9df;">วิเคราะห์ภาพ เสียง และความสมจริงของคลิป</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="dashboard-box">
            <h3>✅ PASS / FAIL</h3>
            <p style="color:#b7c9df;">สรุปผลการตรวจสอบแต่ละคลิปอย่างชัดเจน</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

# -------------------------------
# LOGIN PAGE
# -------------------------------
else:
    st.markdown("""
    <div class="main-wrap">
        <div class="hero-box">
            <div class="left-panel">
                <div class="logo-badge">⚡ CYBER SECURITY ACCESS</div>
                <div class="main-title">CLIP<span>GUARD</span> AI</div>
                <div class="sub-title">
                    ระบบตรวจสอบวิดีโออัจฉริยะในสไตล์ Cyber Tech ล้ำอนาคต
                    พร้อมเอฟเฟกต์แสงเคลื่อนไหว พื้นหลังเรืองแสง และ UI แบบ glassmorphism
                    เหมาะสำหรับต่อยอดเป็นระบบตรวจคลิป PASS / FAIL ของคุณ
                </div>

                <div class="feature-row">
                    <div class="feature-chip">🎞 วิเคราะห์คลิป</div>
                    <div class="feature-chip">🎤 ตรวจเสียงพูด</div>
                    <div class="feature-chip">📦 ตรวจสินค้า</div>
                    <div class="feature-chip">⚡ UI แนวอนาคต</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # วาง card ตรงกลาง
    left, center, right = st.columns([1.2, 0.9, 1.2])

    with center:
        st.markdown("""
        <div class="login-card">
            <div class="card-title">Sign In</div>
            <div class="card-sub"><span class="status-dot"></span>Secure access portal</div>
            <div class="cyber-line"></div>
        """, unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")

        if st.button("LOGIN"):
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

        st.markdown("""
            <div class="helper-text">
                Forgot password? <span>Reset Access</span><br>
                Demo account: <span>admin</span> | Password: <span>1234</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
