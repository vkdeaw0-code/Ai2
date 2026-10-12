
"""AI Video Quality Inspector - Streamlit Cloud Edition."""

import csv
import io
import json
import shutil
import tempfile
import uuid
import zipfile

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)
from pathlib import Path

import streamlit as st

from engine import (
    ROOT,
    analyze_file,
    checksum_and_save
)


st.set_page_config(
    page_title="AI Video Quality Inspector",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1.4rem;
}
[data-testid="stMetricValue"] {
    font-weight: 750;
}
</style>
""", unsafe_allow_html=True)


MAX_TOTAL = 1_000_000_000
MAX_FILES = 120
SAFE_ZIP_SIZE = 150_000_000


def get_secret(name, default=""):
    try:
        return str(
            st.secrets.get(name, default)
        ).strip()
    except (
        FileNotFoundError,
        KeyError,
        AttributeError
    ):
        return default


def file_record(upload, folder):
    suffix = Path(
        upload.name
    ).suffix.lower()

    if suffix not in {
        ".mp4",
        ".mov",
        ".webm"
    }:
        raise ValueError(
            "รองรับเฉพาะ MP4, MOV, WEBM"
        )

    destination = (
        folder
        / f"{uuid.uuid4().hex}{suffix}"
    )

    digest = checksum_and_save(
        upload,
        destination
    )

    return {
        "id": uuid.uuid4().hex,
        "name": upload.name,
        "size": upload.size,
        "path": str(destination),
        "hash": digest
    }


def run_batch(
    uploads,
    mode,
    key,
    model,
    workers
):
    batch_id = uuid.uuid4().hex

    folder = ROOT / batch_id
    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    st.session_state.batch_id = batch_id
    st.session_state.results = []
    st.session_state.busy = True

    progress = st.progress(
        0.0,
        text="กำลังบันทึกไฟล์..."
    )

    notice = st.empty()
    records = []

    try:
        for idx, upload in enumerate(uploads):
            try:
                records.append(
                    file_record(
                        upload,
                        folder
                    )
                )

            except Exception as exc:
                records.append({
                    "id": uuid.uuid4().hex,
                    "name": upload.name,
                    "size": upload.size,
                    "path": "",
                    "hash": "",
                    "result": {
                        "decision": "ERROR",
                        "reason": str(exc),
                        "elapsed": 0,
                        "video_type": "Unknown",
                        "issues": [],
                        "qualified": False
                    }
                })

            progress.progress(
                (idx + 1) / (2 * len(uploads)),
                text=(
                    f"บันทึกไฟล์ "
                    f"{idx + 1}/{len(uploads)}"
                )
            )

        # Skip duplicate video contents in one batch.
        uniques = {}

        for row in records:
            if row.get("hash"):
                uniques.setdefault(
                    row["hash"],
                    row
                )

        futures = {}

        with ThreadPoolExecutor(
            max_workers=workers
        ) as pool:

            for sha, row in uniques.items():
                future = pool.submit(
                    analyze_file,
                    row["path"],
                    sha,
                    mode,
                    key,
                    model
                )

                futures[future] = sha

            outcomes = {}
            completed_unique = 0

            for future in as_completed(futures):
                sha = futures[future]

                try:
                    outcomes[sha] = future.result()

                except Exception as exc:
                    outcomes[sha] = {
                        "decision": "ERROR",
                        "reason": f"Worker: {exc}",
                        "elapsed": 0,
                        "video_type": "Unknown",
                        "issues": [],
                        "qualified": False
                    }

                completed_unique += 1

                current = [
                    dict(
                        row,
                        result=outcomes[row["hash"]]
                    )
                    for row in records
                    if row.get("hash") in outcomes
                ]

                current.extend([
                    row
                    for row in records
                    if "result" in row
                ])

                st.session_state.results = current
                done = len(current)

                progress.progress(
                    .5 + .5 * (
                        done / len(records)
                    ),
                    text=(
                        f"ตรวจเสร็จ "
                        f"{done}/{len(records)} คลิป"
                    )
                )

                notice.info(
                    f"กำลังตรวจ: "
                    f"{completed_unique}/"
                    f"{len(uniques)} ไฟล์ไม่ซ้ำ"
                )

        st.session_state.results = [
            dict(
                row,
                result=outcomes[row["hash"]]
            )
            if row.get("hash")
            else row
            for row in records
        ]

        progress.progress(
            1.0,
            text="เสร็จสิ้น"
        )

        notice.success(
            "การตรวจชุดนี้เสร็จแล้ว"
        )

    finally:
        st.session_state.busy = False


def report_csv(rows):
    output = io.StringIO()

    cols = [
        "filename",
        "size_bytes",
        "decision",
        "inspection_level",
        "qualified",
        "video_type",
        "duration",
        "reason",
        "elapsed",
        "cached",
        "issues"
    ]

    writer = csv.DictWriter(
        output,
        fieldnames=cols
    )

    writer.writeheader()

    for row in rows:
        r = row["result"]

        writer.writerow({
            "filename": row["name"],
            "size_bytes": row["size"],
            "decision": r.get("decision"),
            "inspection_level": r.get(
                "inspection_level",
                "BASIC"
            ),
            "qualified": r.get(
                "qualified",
                False
            ),
            "video_type": r.get(
                "video_type",
                ""
            ),
            "duration": r.get("duration"),
            "reason": r.get(
                "reason",
                ""
            ),
            "elapsed": r.get("elapsed"),
            "cached": r.get(
                "cached",
                False
            ),
            "issues": json.dumps(
                r.get("issues", []),
                ensure_ascii=False
            )
        })

    return output.getvalue().encode(
        "utf-8-sig"
    )


def make_zip(rows):
    stream = io.BytesIO()

    with zipfile.ZipFile(
        stream,
        "w",
        compression=zipfile.ZIP_STORED
    ) as z:

        for i, row in enumerate(rows):
            p = Path(row["path"])

            if p.exists():
                z.write(
                    p,
                    arcname=(
                        f"{i + 1:03d}_"
                        f"{Path(row['name']).name}"
                    )
                )

    return stream.getvalue()


st.title(
    "🎬 AI Video Quality Inspector"
)

st.caption(
    "GitHub + Streamlit Cloud Edition "
    "• ตรวจเป็นชุด • PASS / FAIL "
    "• จัดการผลในหน้าเว็บ"
)

st.warning(
    "**โปรดอ่าน:** หากไม่มี Gemini API Key "
    "โปรแกรมจะตรวจได้เฉพาะข้อบกพร่องทางเทคนิค "
    "เช่น ภาพมืดหรือเสียงแตก "
    "ผล PASS ในโหมดนี้เป็นเพียง PASS เบื้องต้น "
    "ไม่ได้ยืนยันว่ามือ นิ้ว หรือสินค้าถูกต้อง"
)


api_key = get_secret(
    "GEMINI_API_KEY"
)

model = get_secret(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)


with st.sidebar:
    st.header(
        "⚙️ ตั้งค่าการตรวจ"
    )

    mode = st.selectbox(
        "ความละเอียด",
        [
            "Balanced",
            "Fast",
            "Deep"
        ],
        index=0,
        help=(
            "Fast 10 เฟรม, "
            "Balanced 20 เฟรม, "
            "Deep 30 เฟรมต่อคลิป"
        )
    )

    ai_on = st.checkbox(
        "ใช้ Gemini Vision AI",
        value=bool(api_key),
        disabled=not api_key
    )

    workers = st.slider(
        "จำนวนคลิปที่ตรวจพร้อมกัน",
        1,
        3,
        2
    )

    if ai_on:
        st.success(
            f"เชื่อมต่อโหมด AI: {model}"
        )

        st.caption(
            "ใช้เฉพาะโมเดลที่บัญชีของคุณมีสิทธิ์ "
            "และอาจมีโควตาหรือค่าใช้จ่าย "
            "ตามบัญชี API"
        )

    else:
        st.info(
            "โหมด BASIC: "
            "ใช้ OpenCV/FFmpeg ใน Streamlit "
            "ไม่ต้องมี API Key"
        )

    st.caption(
        "คลิปต่าง ๆ เก็บชั่วคราว "
        "บนเซิร์ฟเวอร์ Streamlit; "
        "อาจหายเมื่อแอปรีสตาร์ต"
    )

    space = shutil.disk_usage(
        tempfile.gettempdir()
    )

    st.metric(
        "พื้นที่ดิสก์ว่าง",
        f"{space.free / 1e9:.1f} GB"
    )


if "results" not in st.session_state:
    st.session_state.results = []

if "busy" not in st.session_state:
    st.session_state.busy = False


st.subheader(
    "1. อัปโหลดวิดีโอ"
)

files = st.file_uploader(
    "เลือกคลิป MP4, MOV หรือ WEBM "
    "(เลือกหลายไฟล์ได้)",
    type=[
        "mp4",
        "mov",
        "webm"
    ],
    accept_multiple_files=True
)


if files:
    total = sum(
        x.size
        for x in files
    )

    a, b, c = st.columns(3)

    a.metric(
        "ไฟล์ที่เลือก",
        len(files)
    )

    b.metric(
        "ขนาดรวม",
        f"{total / 1e6:.1f} MB"
    )

    c.metric(
        "เพดานต่อชุด",
        "1,000 MB"
    )

    if total > MAX_TOTAL:
        st.error(
            "ไฟล์ชุดนี้เกิน 1 GB "
            "โปรดแบ่งเป็นหลายชุด"
        )

    elif len(files) > MAX_FILES:
        st.error(
            "เกิน 120 คลิปต่อชุด "
            "โปรดแบ่งเป็นหลายชุด"
        )

    else:
        if total > 250_000_000:
            st.warning(
                "ชุดนี้ค่อนข้างใหญ่สำหรับ "
                "Streamlit Cloud ฟรี "
                "อาจถูกจำกัด RAM "
                "แม้โปรแกรมตั้งรับสูงสุด 1 GB"
            )

        if st.button(
            "▶ เริ่มตรวจทั้งหมด",
            type="primary",
            disabled=st.session_state.busy
        ):
            run_batch(
                files,
                mode,
                api_key if ai_on else "",
                model,
                workers
            )

else:
    st.info(
        "เลือกไฟล์ก่อน "
        "แล้วกดปุ่มเริ่มตรวจทั้งหมด"
    )


rows = st.session_state.results

st.divider()

st.subheader(
    "2. ผลการตรวจ"
)


if not rows:
    st.caption(
        "ยังไม่มีผลการตรวจในเซสชันนี้"
    )

else:
    passed = sum(
        r["result"].get("decision") == "PASS"
        for r in rows
    )

    failed = sum(
        r["result"].get("decision") == "FAIL"
        for r in rows
    )

    errors = sum(
        r["result"].get("decision") == "ERROR"
        for r in rows
    )

    unverified = sum(
        r["result"].get("decision") == "PASS"
        and not r["result"].get(
            "qualified",
            False
        )
        for r in rows
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "ตรวจแล้ว",
        len(rows)
    )

    c2.metric(
        "PASS",
        passed
    )

    c3.metric(
        "FAIL",
        failed
    )

    c4.metric(
        "ERROR",
        errors
    )

    if unverified:
        st.warning(
            f"มี PASS เบื้องต้น {unverified} คลิป "
            "ที่ยัง **ไม่ได้ตรวจข้อผิดเพี้ยน "
            "ของมือและสินค้าด้วย Vision AI**"
        )

    filt = st.selectbox(
        "กรองผล",
        [
            "ทั้งหมด",
            "PASS",
            "FAIL",
            "ERROR"
        ]
    )

    word = st.text_input(
        "ค้นหาชื่อคลิป"
    )

    filtered = [
        r
        for r in rows
        if (
            filt == "ทั้งหมด"
            or r["result"].get("decision") == filt
        )
        and word.lower() in r["name"].lower()
    ]

    st.dataframe(
        [
            {
                "ไฟล์": r["name"],
                "ผล": r["result"].get(
                    "decision",
                    "ERROR"
                ),
                "ระดับ": r["result"].get(
                    "inspection_level",
                    "BASIC"
                ),
                "ประเภท": r["result"].get(
                    "video_type",
                    "Unknown"
                ),
                "เหตุผล": r["result"].get(
                    "reason",
                    ""
                ),
                "เวลา (วิ.)": r["result"].get(
                    "elapsed",
                    0
                )
            }
            for r in filtered
        ],
        hide_index=True,
        use_container_width=True
    )

    st.download_button(
        "⬇ ดาวน์โหลดรายงาน CSV",
        report_csv(rows),
        "video_inspection_results.csv",
        mime="text/csv"
    )

    st.download_button(
        "⬇ ดาวน์โหลดรายงาน JSON",
        json.dumps(
            [
                {
                    "name": r["name"],
                    **r["result"]
                }
                for r in rows
            ],
            ensure_ascii=False,
            indent=2
        ),
        "video_inspection_results.json",
        mime="application/json"
    )

    st.subheader(
        "3. ดาวน์โหลดวิดีโอ"
    )

    options = {
        (
            f"{r['name']} | "
            f"{r['result'].get('decision')} | "
            f"{r['id'][:6]}"
        ): r

        for r in filtered

        if r.get("path")
        and Path(r["path"]).exists()
    }

    selected = st.multiselect(
        "เลือกคลิปที่จะดาวน์โหลด",
        list(options)
    )

    choice = [
        options[x]
        for x in selected
    ]

    size = sum(
        r["size"]
        for r in choice
    )

    st.caption(
        f"เลือก {len(choice)} ไฟล์ "
        f"รวม {size / 1e6:.1f} MB — "
        "จำกัด ZIP ที่ 150 MB "
        "เพื่อป้องกัน RAM เต็ม"
    )

    if choice and size <= SAFE_ZIP_SIZE:
        st.download_button(
            "⬇ ดาวน์โหลดคลิปที่เลือก (ZIP)",
            make_zip(choice),
            "selected_clips.zip",
            mime="application/zip"
        )

    elif size > SAFE_ZIP_SIZE:
        st.warning(
            "เลือกชุดย่อยรวมไม่เกิน 150 MB "
            "แล้วดาวน์โหลดหลายครั้ง"
        )

    st.subheader(
        "4. ดูรายละเอียดคลิป"
    )

    page = st.number_input(
        "หน้าผลลัพธ์ (หน้าละ 8 คลิป)",
        min_value=1,
        max_value=max(
            1,
            (len(filtered) + 7) // 8
        ),
        value=1
    )

    for r in filtered[
        (page - 1) * 8:page * 8
    ]:
        decision = r["result"].get(
            "decision",
            "ERROR"
        )

        icon = {
            "PASS": "✅",
            "FAIL": "❌",
            "ERROR": "⚠️"
        }.get(
            decision,
            "❓"
        )

        with st.expander(
            f"{icon} {r['name']} — {decision}"
        ):
            details = r["result"]

            st.write(
                details.get(
                    "reason",
                    ""
                )
            )

            st.write(
                "**ประเภท:**",
                details.get(
                    "video_type",
                    "Unknown"
                ),
                " | **ระยะเวลา:**",
                details.get(
                    "duration"
                ),
                " | **ความละเอียด:**",
                details.get(
                    "resolution"
                )
            )

            if details.get("notes"):
                st.write(
                    "**หมายเหตุ:**",
                    "; ".join(
                        details["notes"]
                    )
                )

            if details.get("issues"):
                st.json(
                    details["issues"]
                )

            thumb = (
                Path(
                    r["path"] + ".jpg"
                )
                if r.get("path")
                else None
            )

            if thumb and thumb.exists():
                st.image(
                    str(thumb),
                    width=260
                )

            if (
                r.get("path")
                and Path(
                    r["path"]
                ).exists()
            ):
                if st.checkbox(
                    "เล่นวิดีโอ",
                    key="play_" + r["id"]
                ):
                    st.video(
                        r["path"]
                    )


st.caption(
    "หมายเหตุ: Streamlit Community Cloud "
    "เป็นโฮสต์ทรัพยากรจำกัด "
    "เหมาะสำหรับเริ่มทดสอบ "
    "ไม่ใช่ระบบประมวลผลวิดีโอปริมาณมหาศาล "
    "ที่มี SLA"
)
