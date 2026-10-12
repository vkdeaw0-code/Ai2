
"""ClipWise AI QC — เว็บใหม่สำหรับ Streamlit Community Cloud."""
from __future__ import annotations

import csv
import hashlib
import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from qc_engine import (
    ALLOWED_SUFFIXES, MAX_CHUNK_BYTES, MAX_ROUND_BYTES, inspect
)

st.set_page_config(page_title="ClipWise AI QC", page_icon="🎬", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 1.5rem;}
[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.20);border-radius:14px;padding:14px;}
[data-testid="stFileUploader"] {border-radius:14px;}
</style>
""", unsafe_allow_html=True)

for key, default in {
    "records": [], "round_bytes": 0, "upload_cycle": 0, "round_cycle": 0, "done": set(), "catalog": {}
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def read_catalog(uploaded):
    if uploaded is None:
        return st.session_state.catalog
    content = uploaded.getvalue()
    if len(content) > 2_000_000:
        raise ValueError("CSV มีขนาดเกิน 2 MB")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {"filename", "product", "brand"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("CSV ต้องมี filename,product,brand")
    result = {}
    for row in reader:
        name = Path((row.get("filename") or "").strip()).name
        if name:
            result[name] = {
                "product": row.get("product", ""), "brand": row.get("brand", ""),
                "details": row.get("details", ""), "mode": row.get("mode", ""),
            }
    return result


def csv_safe(value):
    s = str(value if value is not None else "")
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s


def result_csv(rows):
    cols = ["file", "status", "reason", "seconds", "time_s", "confidence",
            "scene", "transcript", "issues"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=cols)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: csv_safe(row.get(k, "")) for k in cols})
    return out.getvalue().encode("utf-8-sig")


st.title("🎬 ClipWise AI QC")
st.caption("ตรวจคุณภาพคลิป AI • ภาพ + เสียงภาษาไทย + ความตรงกันของสินค้า • ออกผลพร้อมเหตุผล")

with st.sidebar:
    st.header("⚙️ ตั้งค่าการตรวจ")
    try:
        saved_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        saved_key = ""
    if saved_key:
        st.success("อ่าน Gemini API key จาก Streamlit Secrets แล้ว")
        api_key = saved_key
    else:
        api_key = st.text_input("Gemini API key", type="password")
    model = st.selectbox("โมเดล AI", ["gemini-3.8-flash", "gemini-3.5-flash-lite"])
    st.caption("Flash ตรวจละเอียดกว่าโดยทั่วไป; Lite เหมาะเมื่อต้องการลดเวลา/โควตา แต่ต้องวัดผลกับคลิปจริง")
    mode_name = st.selectbox("ประเภทคลิป", ["อัตโนมัติ", "คนยืนพูดรีวิว", "โชว์สินค้า"])
    mode = {"อัตโนมัติ": "AUTO", "คนยืนพูดรีวิว": "TALK", "โชว์สินค้า": "PRODUCT"}[mode_name]
    strict = st.slider("ความเข้มงวดต่อหลักฐานผิดพลาด", 0.65, 0.95, 0.78, 0.01,
                       help="ต่ำ = กล้าตัด FAIL มากขึ้น แต่เสี่ยงคัดคลิปดีทิ้ง")
    extra_frames = st.checkbox("ตรวจภาพเสริมช่วงเคลื่อนไหว", value=True,
                               help="ส่งภาพเพิ่มเติม 4 ภาพให้ AI เพื่อช่วยมองปัญหาที่เกิดระหว่างวิดีโอ")
    st.divider()
    st.info("หากไม่มี API key โปรแกรมจะตรวจไฟล์พื้นฐานได้ แต่ไม่เดาว่า PASS/FAIL: ให้ REVIEW")
    st.caption("คีย์แนะนำให้ตั้งใน Streamlit → App settings → Secrets เป็น GEMINI_API_KEY")

st.subheader("📊 ภาพรวมรอบงาน")
rows = st.session_state.records
counts = {k: sum(r["status"] == k for r in rows) for k in ("PASS", "FAIL", "REVIEW", "ERROR")}
c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 ผ่าน", counts["PASS"])
c2.metric("🔴 ไม่ผ่าน", counts["FAIL"])
c3.metric("🟠 ตรวจซ้ำ", counts["REVIEW"])
c4.metric("⚪ ข้อผิดพลาดระบบ", counts["ERROR"])
st.progress(min(1.0, st.session_state.round_bytes / MAX_ROUND_BYTES),
            text=f"รวมไฟล์ที่รับเข้ารอบ: {st.session_state.round_bytes / 1e6:.1f} / 1,000 MB")

with st.expander("ข้อมูลสินค้าอ้างอิง (ช่วยตรวจชื่อ/ยี่ห้อให้ตรง) — ไม่บังคับ"):
    st.caption("CSV: filename,product,brand,details,mode • ค่า mode ต่อคลิป AUTO / TALK / PRODUCT")
    catalog_file = st.file_uploader("อัปโหลดรายการสินค้า CSV", type=["csv"], key="catalog_file")
    if catalog_file is not None:
        try:
            st.session_state.catalog = read_catalog(catalog_file)
            st.success(f"นำเข้าข้อมูลสินค้า {len(st.session_state.catalog)} รายการ")
        except Exception as exc:
            st.error(str(exc))
    st.download_button("ดาวน์โหลดตัวอย่าง CSV", "filename,product,brand,details,mode\nclip1.mp4,กาแฟ,ยี่ห้อจริง,รสหวานน้อย,TALK\n".encode("utf-8-sig"),
                       file_name="catalog_example.csv", mime="text/csv")

st.subheader("📥 เพิ่มคลิปเข้ารอบ")
st.caption("สะสมได้สูงสุด 1 GB ต่อรอบ โดยแบ่งอัปโหลดชุดย่อย ≤120 MB เพื่อประหยัด RAM ของ Streamlit Cloud ฟรี")
files = st.file_uploader("เลือกวิดีโอ MP4 / MOV / WEBM หลายไฟล์", type=["mp4", "mov", "m4v", "webm"],
                         accept_multiple_files=True, key=f"upload_{st.session_state.upload_cycle}")
selected = sum(f.size for f in (files or []))
st.write(f"เลือก {len(files or [])} ไฟล์ • {selected / 1e6:.1f} MB ในชุดนี้")
excess = selected > MAX_CHUNK_BYTES or st.session_state.round_bytes + selected > MAX_ROUND_BYTES
if selected > MAX_CHUNK_BYTES:
    st.error("ชุดนี้เกิน 120 MB โปรดแบ่งเลือกไฟล์ให้น้อยลง (หนึ่งรอบยังสะสมได้สูงสุด 1 GB)")
if st.session_state.round_bytes + selected > MAX_ROUND_BYTES:
    st.error("รวมเกินเพดาน 1 GB ของรอบนี้ กรุณาเริ่มรอบใหม่")
if not api_key:
    st.warning("ยังไม่มี Gemini API key: สามารถทดสอบการอ่านไฟล์ แต่ทุกคลิปจะเป็น REVIEW")

if st.button("▶ เริ่มตรวจคลิปที่เลือก", type="primary", disabled=not files or excess,
             use_container_width=True):
    bar = st.progress(0, text="เริ่มตรวจ...")
    info_line = st.empty()
    for i, up in enumerate(files, 1):
        info_line.info(f"กำลังตรวจ {i}/{len(files)} : {up.name}")
        # บันทึกทีละไฟล์และคืนทรัพยากรหลังตรวจ; ไม่มีการโหลดทุกคลิปพร้อมกันใน engine
        with tempfile.TemporaryDirectory(prefix="clipwise_") as tmp:
            target = Path(tmp) / ("input" + Path(up.name).suffix.lower())
            sha = hashlib.sha256()
            try:
                if target.suffix not in ALLOWED_SUFFIXES:
                    raise ValueError("รูปแบบไฟล์ไม่รองรับ")
                with target.open("wb") as dst:
                    up.seek(0)
                    while True:
                        block = up.read(1024 * 1024)
                        if not block:
                            break
                        sha.update(block)
                        dst.write(block)
                catalog = st.session_state.catalog.get(up.name, {})
                this_mode = catalog.get("mode", "")
                if this_mode not in ("AUTO", "TALK", "PRODUCT"):
                    this_mode = mode
                fingerprint = hashlib.sha256(
                    (sha.hexdigest() + repr((catalog, this_mode, model, strict, extra_frames, bool(api_key)))).encode()
                ).hexdigest()
                if fingerprint in st.session_state.done:
                    st.info(f"ข้ามไฟล์ที่ตรวจแล้ว: {up.name}")
                    bar.progress(i / len(files), text=f"เสร็จ {i}/{len(files)}")
                    continue
                result = inspect(target, up.name, api_key, model,
                                 catalog, this_mode, strict, extra_frames)
            except Exception as exc:
                result = {
                    "file": up.name, "status": "ERROR", "reason": str(exc)[:180],
                    "seconds": "", "resolution": "", "time_s": "", "transcript": "",
                    "scene": "", "summary": "", "confidence": 0.0, "issues": []
                }
            st.session_state.records.append(result)
            st.session_state.round_bytes += up.size
            if result["status"] != "ERROR":
                st.session_state.done.add(fingerprint)
        bar.progress(i / len(files), text=f"เสร็จ {i}/{len(files)}")
    info_line.success("ตรวจชุดนี้เสร็จแล้ว ผลถูกรวมในตารางด้านล่าง")
    # เปลี่ยน key เพื่อเคลียร์ไฟล์ upload จาก widget ก่อนเลือกชุดใหม่
    st.session_state.upload_cycle += 1
    st.rerun()

st.subheader("🧾 ผลตรวจแยกรายคลิป")
if not rows:
    st.info("ยังไม่มีผลตรวจ — อัปโหลดวิดีโอแล้วกดเริ่มตรวจ")
else:
    view = pd.DataFrame([{
        "ชื่อคลิป": r["file"],
        "ผลตรวจ": {"PASS": "🟢 ผ่าน", "FAIL": "🔴 ไม่ผ่าน", "REVIEW": "🟠 ตรวจซ้ำ", "ERROR": "⚪ ERROR"}[r["status"]],
        "เหตุผล": r["reason"],
        "คลิป (วินาที)": r.get("seconds", ""),
        "เวลาตรวจ (วินาที)": r.get("time_s", ""),
    } for r in rows])
    filter_by = st.radio("แสดงผล", ["ทั้งหมด", "ผ่าน", "ไม่ผ่าน", "ตรวจซ้ำ", "ERROR"], horizontal=True)
    if filter_by != "ทั้งหมด":
        view = view[view["ผลตรวจ"].str.contains(filter_by, regex=False)]
    st.dataframe(view, use_container_width=True, hide_index=True)
    truth_rows = []
    st.markdown("**🔎 รายละเอียดและผลจริงจากคนตรวจ**")
    for n, r in enumerate(rows):
        with st.expander(f"{r['file']} | {r['status']} | {r.get('time_s','-')} วิ", expanded=False):
            st.write("**สรุป:**", r["reason"])
            st.write("**เสียงพูด:**", r.get("transcript") or "ไม่มีผลถอดเสียงที่ยืนยันได้")
            st.write("**ภาพ:**", r.get("scene") or "ไม่มีข้อมูล")
            for issue in r.get("issues", []):
                st.write(f"{issue.get('second',0):.1f}s | {issue.get('category','')} | {issue.get('severity','')} | {issue.get('detail','')}")
            human = st.selectbox("ผลที่คุณตัดสินด้วยตนเอง", ["ยังไม่กำหนด", "PASS", "FAIL"],
                                 key=f"truth_{st.session_state.round_cycle}_{n}")
            if human != "ยังไม่กำหนด":
                truth_rows.append({"filename": r["file"], "truth": human, "predicted": r["status"]})
    st.download_button("⬇ ดาวน์โหลดผล CSV", result_csv(rows), file_name="clipwise_results.csv", mime="text/csv")
    if truth_rows:
        correct = sum(x["truth"] == x["predicted"] for x in truth_rows)
        false_pass = sum(x["truth"] == "FAIL" and x["predicted"] == "PASS" for x in truth_rows)
        st.caption(f"เทียบกับผลคนตรวจ: ตรง {correct}/{len(truth_rows)} • คลิปผิดที่หลุด PASS {false_pass}")
        st.download_button("⬇ ดาวน์โหลดเฉลยของคุณ", pd.DataFrame([{k: csv_safe(v) for k,v in x.items()} for x in truth_rows]).to_csv(index=False).encode("utf-8-sig"),
                           file_name="human_labels.csv", mime="text/csv")
    a, b = st.columns(2)
    with a:
        if st.button("🔄 เริ่มรอบใหม่ (ล้างผลทั้งหมด)"):
            st.session_state.records = []
            st.session_state.round_bytes = 0
            st.session_state.done = set()
            st.session_state.upload_cycle += 1
            st.session_state.round_cycle += 1
            st.rerun()
    with b:
        st.caption("ผลจะอยู่ในเซสชันนี้เท่านั้น กรุณาดาวน์โหลด CSV ก่อนปิดหรือรีสตาร์ตแอป")
