
"""Video QA engine for Streamlit Community Cloud."""
import base64
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import requests

ROOT = Path(tempfile.gettempdir()) / "ai_video_quality_web"
ROOT.mkdir(parents=True, exist_ok=True)
DB = ROOT / "results.sqlite3"
RULE_VERSION = "web-1.1"
DB_LOCK = threading.Lock()
API_LOCK = threading.Lock()
NEXT_API_TIME = [0.0]


def init_db():
    with sqlite3.connect(DB, timeout=20) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()


def checksum_and_save(upload, destination):
    """Save an uploaded file in chunks and calculate SHA-256."""
    digest = hashlib.sha256()
    destination = Path(destination)
    temp_path = destination.with_suffix(
        destination.suffix + ".part"
    )

    upload.seek(0)
    try:
        with open(temp_path, "wb") as out:
            while True:
                block = upload.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
                digest.update(block)

        os.replace(temp_path, destination)
    finally:
        upload.seek(0)
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    return digest.hexdigest()


def cache_get(key):
    init_db()
    with DB_LOCK, sqlite3.connect(DB, timeout=20) as conn:
        row = conn.execute(
            "SELECT result_json FROM cache WHERE cache_key=?",
            (key,)
        ).fetchone()

    return json.loads(row[0]) if row else None


def cache_put(key, result):
    init_db()
    with DB_LOCK, sqlite3.connect(DB, timeout=20) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
            (
                key,
                json.dumps(result, ensure_ascii=False),
                time.time()
            )
        )
        conn.commit()


def _frame_at(cap, second):
    cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
    ok, frame = cap.read()

    if not ok or frame is None:
        return None

    h, w = frame.shape[:2]

    if w > 560:
        frame = cv2.resize(
            frame,
            (560, max(1, int(560 * h / w))),
            interpolation=cv2.INTER_AREA
        )

    return frame


def inspect_frames(path, mode):
    cap = cv2.VideoCapture(str(path))

    if not cap.isOpened():
        raise ValueError(
            "เปิดไฟล์วิดีโอไม่ได้ "
            "(อาจเป็นไฟล์เสียหรือ codec ไม่รองรับ)"
        )

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        if fps <= 0 or count <= 0:
            raise ValueError("อ่าน FPS หรือจำนวนเฟรมไม่ได้")

        duration = count / fps

        if duration <= 0 or duration > 600:
            raise ValueError(
                "ความยาววิดีโอผิดปกติหรือยาวเกินที่ระบบรับได้"
            )

        amount = {
            "Fast": 10,
            "Balanced": 20,
            "Deep": 30
        }[mode]

        times = np.linspace(
            0.15,
            max(.15, duration - .15),
            amount
        )

        frames = []
        valid_times = []

        for t in times:
            image = _frame_at(cap, float(t))

            if image is not None:
                frames.append(image)
                valid_times.append(round(float(t), 2))

        if len(frames) < 3:
            raise ValueError(
                "อ่านเฟรมไม่เพียงพอสำหรับการตรวจ"
            )

    finally:
        cap.release()

    black = []
    white = []
    blurry = []
    faces = 0

    face_classifier = cv2.CascadeClassifier(
        cv2.data.haarcascades
        + "haarcascade_frontalface_default.xml"
    )

    for idx, frame in enumerate(frames):
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        mean = float(gray.mean())
        sharpness = float(
            cv2.Laplacian(
                gray,
                cv2.CV_64F
            ).var()
        )

        if mean < 13:
            black.append(valid_times[idx])

        if mean > 246:
            white.append(valid_times[idx])

        if sharpness < 10:
            blurry.append(valid_times[idx])

        if idx % 4 == 0 and not face_classifier.empty():
            small = cv2.resize(
                gray,
                None,
                fx=.65,
                fy=.65
            )

            faces += len(
                face_classifier.detectMultiScale(
                    small,
                    scaleFactor=1.15,
                    minNeighbors=4,
                    minSize=(28, 28)
                )
            )

    critical = []
    warnings = []

    if len(black) / len(frames) >= .65:
        critical.append({
            "type": "ภาพมืดเกือบทั้งคลิป",
            "timestamp": black[0]
        })
    elif len(black) / len(frames) >= .25:
        warnings.append(
            "หลายช่วงของคลิปมืดมาก"
        )

    if len(white) / len(frames) >= .75:
        critical.append({
            "type": "ภาพขาวจ้าเกือบทั้งคลิป",
            "timestamp": white[0]
        })

    if len(blurry) / len(frames) >= .9:
        warnings.append(
            "ภาพอาจเบลอทั้งคลิป; "
            "ต้องดูสินค้าและบริบทจริง"
        )

    if not 6 <= duration <= 20:
        warnings.append(
            f"ความยาว {duration:.1f} วินาที "
            "(เป้าหมายประมาณ 10 วินาที)"
        )

    return {
        "duration": round(duration, 2),
        "fps": round(fps, 2),
        "resolution": f"{width}x{height}",
        "frames": frames,
        "times": valid_times,
        "critical": critical,
        "warnings": warnings,
        "type_guess": (
            "Human Presenter / Mixed"
            if faces
            else "Product Only / Hands / Mixed"
        )
    }


def inspect_audio(path):
    """Extract PCM audio and measure basic signal defects."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    args = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(path),
        "-vn",
        "-t", "20",
        "-ac", "1",
        "-ar", "16000",
        "-f", "s16le",
        "pipe:1"
    ]

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=35,
            check=False
        )
    except subprocess.TimeoutExpired:
        return {
            "present": False,
            "warning": "ดึงเสียงไม่สำเร็จ (หมดเวลา)",
            "pcm": b""
        }

    if proc.returncode != 0 or not proc.stdout:
        return {
            "present": False,
            "warning": (
                "ไม่มีเสียง "
                "หรือไม่สามารถอ่านแทร็กเสียง"
            ),
            "pcm": b""
        }

    pcm = proc.stdout

    sample = np.frombuffer(
        pcm,
        dtype=np.int16
    ).astype(np.float32)

    peak = float(
        np.max(np.abs(sample))
    ) / 32768

    rms = float(
        np.sqrt(
            np.mean(
                (sample / 32768.0) ** 2
            )
        )
    )

    clipped = float(
        np.mean(
            np.abs(sample) >= 32750
        )
    )

    critical = []

    if clipped > .2 and rms > .25:
        critical.append({
            "type": (
                "เสียงแตกหรือ clipping รุนแรง"
            ),
            "timestamp": None
        })

    return {
        "present": True,
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "clipped_ratio": round(clipped, 4),
        "critical": critical,
        "warning": (
            "เสียงเบามาก"
            if rms < .003
            else ""
        ),
        "pcm": pcm
    }


def _contact_sheet(
    frames,
    times,
    indices,
    columns=3,
    box_w=336,
    box_h=222
):
    from PIL import Image, ImageDraw

    rows = (
        len(indices) + columns - 1
    ) // columns

    out = Image.new(
        "RGB",
        (box_w * columns, box_h * rows),
        (19, 29, 45)
    )

    draw = ImageDraw.Draw(out)

    for index, frame_index in enumerate(indices):
        frame = frames[frame_index]

        im = Image.fromarray(
            cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )
        )

        im.thumbnail(
            (box_w - 12, box_h - 28)
        )

        x = (
            (index % columns) * box_w
            + (box_w - im.width) // 2
        )

        y = (
            (index // columns) * box_h
            + 22
        )

        out.paste(im, (x, y))

        draw.text(
            (
                (index % columns) * box_w + 10,
                (index // columns) * box_h + 5
            ),
            f"t={times[frame_index]:.2f}s",
            fill="white"
        )

    out_buffer = io.BytesIO()

    out.save(
        out_buffer,
        format="JPEG",
        quality=81,
        optimize=True
    )

    return out_buffer.getvalue()


def make_thumbnails(path, frames, times):
    overview_indices = np.linspace(
        0,
        len(frames) - 1,
        min(len(frames), 12),
        dtype=int
    ).tolist()

    overview = _contact_sheet(
        frames,
        times,
        overview_indices
    )

    # Select extra detail frames based on visual change.
    # A visual change is not automatically a defect.
    gray = [
        cv2.resize(
            cv2.cvtColor(f, cv2.COLOR_BGR2GRAY),
            (120, 80)
        )
        for f in frames
    ]

    changes = [
        (
            float(
                np.mean(
                    cv2.absdiff(
                        gray[i],
                        gray[i - 1]
                    )
                )
            ),
            i
        )
        for i in range(1, len(frames))
    ]

    picks = {
        0,
        len(frames) - 1
    }

    for _, idx in sorted(
        changes,
        reverse=True
    ):
        picks.add(idx)

        if len(picks) >= min(
            6,
            len(frames)
        ):
            break

    details = _contact_sheet(
        frames,
        times,
        sorted(picks),
        columns=2,
        box_w=560,
        box_h=360
    )

    thumb = cv2.resize(
        frames[len(frames) // 2],
        (240, 135)
    )

    thumb_name = str(path) + ".jpg"

    cv2.imwrite(
        thumb_name,
        thumb
    )

    return [overview, details], thumb_name


PROMPT = """
You are a strict but fair QUALITY INSPECTOR
for ~10-second AI-generated PRODUCT AD videos.

Assess whether a NORMAL viewer would notice
significant defects, not whether the video looks
AI-generated.

The attachments include overview frames and
a detailed sheet of selected moments,
all time-stamped. They are NOT full motion video.

An audio clip may be attached.

Never claim to have checked lip sync or exact motion
if only frames are supplied.

Judge various products:
boxes, bags, coffee, toys, sports equipment,
cups, bottles, and bulk cartons.

Do not assume an object's actual physical size
without a reference.

Judge:
- human faces and anatomy
- hands and fingers
- hand-product contact
- packaging and labels
- text and logos
- product identity
- product shape consistency
- scene continuity
- object interaction
- visual commercial quality

Respect perspective changes, cuts, zoom,
camera motion, and intentional artistic effects.

Do NOT call these a defect by themselves.

For minor imperfections that will not distract
normal viewers, return PASS.

For clear and severe distortions, return FAIL.

Where evidence is ambiguous,
avoid inventing a defect.

Consider several moderately serious visible
problems together.

If audio is attached, assess:
- gross speech intelligibility
- Thai pronunciation only if audibly verifiable
- clipping and noise
- product-related speech and visual coherence

For speech-to-product mismatch,
only use what is visibly and audibly verifiable.

Return JSON object ONLY with exactly these keys:

{
  "decision": "PASS or FAIL",
  "video_type": "Human Presenter or Product With Hands or Product Only or Mixed",
  "reason_th": "short Thai reason",
  "issues": [
    {
      "time": 0.0,
      "severity": "moderate or critical",
      "description_th": "evidence-based Thai defect"
    }
  ]
}

Do not invent defects or timestamps.
List no issues when PASS is justified.
"""


def _api_wait(seconds):
    with API_LOCK:
        delay = max(
            0.0,
            NEXT_API_TIME[0] - time.monotonic()
        )

        NEXT_API_TIME[0] = max(
            time.monotonic(),
            NEXT_API_TIME[0]
        ) + seconds

    if delay:
        time.sleep(delay)


def ask_gemini(
    sheet,
    audio,
    api_key,
    model,
    gap_seconds=8
):
    _api_wait(gap_seconds)

    parts = [
        {"text": PROMPT}
    ]

    for jpeg in sheet:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(
                    jpeg
                ).decode()
            }
        })

    if (
        audio.get("present")
        and audio.get("pcm")
    ):
        import wave

        stream = io.BytesIO()

        with wave.open(stream, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(audio["pcm"])

        parts.append({
            "inline_data": {
                "mime_type": "audio/wav",
                "data": base64.b64encode(
                    stream.getvalue()
                ).decode()
            }
        })

    body = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                headers={
                    "x-goog-api-key": api_key
                },
                json=body,
                timeout=(10, 100)
            )

        except requests.RequestException as exc:
            if attempt < 2:
                time.sleep(
                    2 ** attempt * 3
                )
                continue

            raise RuntimeError(
                f"เชื่อมต่อ AI ไม่ได้: {exc}"
            ) from exc

        if (
            resp.status_code in (
                429, 500, 502, 503, 504
            )
            and attempt < 2
        ):
            time.sleep(
                6 * (2 ** attempt)
            )
            continue

        if not resp.ok:
            try:
                detail = resp.json().get(
                    "error", {}
                ).get(
                    "message", ""
                )[:220]

            except ValueError:
                detail = resp.text[:220]

            raise RuntimeError(
                f"Gemini HTTP {resp.status_code}: "
                f"{detail}"
            )

        try:
            content = resp.json()[
                "candidates"
            ][0]["content"]["parts"]

            response_text = "".join(
                p.get("text", "")
                for p in content
            )

            data = json.loads(
                response_text.strip()
                .removeprefix("```json")
                .removesuffix("```")
                .strip()
            )

        except (
            KeyError,
            IndexError,
            ValueError,
            TypeError
        ) as exc:
            raise RuntimeError(
                "AI ไม่ส่ง JSON ที่ถูกต้อง"
            ) from exc

        if data.get("decision") not in (
            "PASS",
            "FAIL"
        ):
            raise RuntimeError(
                "AI ส่งผลที่ไม่ใช่ PASS หรือ FAIL"
            )

        return data

    raise RuntimeError(
        "API ยังไม่พร้อมหรือโควตาไม่เพียงพอ"
    )


def analyze_file(
    path,
    sha256,
    mode,
    api_key="",
    model="gemini-3.5-flash-lite"
):
    start = time.monotonic()
    use_ai = bool(api_key)

    key = hashlib.sha256(
        (
            f"{sha256}|{mode}|{RULE_VERSION}|"
            f"{model if use_ai else 'BASIC'}"
        ).encode()
    ).hexdigest()

    prior = cache_get(key)

    if prior is not None:
        result = dict(prior)
        result["cached"] = True
        result["elapsed"] = 0.0
        return result

    result = {
        "decision": "ERROR",
        "reason": "",
        "issues": [],
        "video_type": "Unknown",
        "duration": None,
        "resolution": "",
        "elapsed": 0.0,
        "cached": False,
        "inspection_level": (
            "AI" if use_ai else "BASIC"
        )
    }

    try:
        picture = inspect_frames(
            path,
            mode
        )

        result["duration"] = picture["duration"]
        result["resolution"] = picture["resolution"]
        result["video_type"] = picture["type_guess"]

        audio = inspect_audio(path)

        sheet, _ = make_thumbnails(
            path,
            picture["frames"],
            picture["times"]
        )

        issues = (
            list(picture["critical"])
            + audio.get("critical", [])
        )

        notes = list(
            picture["warnings"]
        )

        if audio.get("warning"):
            notes.append(
                audio["warning"]
            )

        if issues:
            result["decision"] = "FAIL"

            result["reason"] = "; ".join(
                i["type"]
                for i in issues
            )

            result["issues"] = issues

        elif use_ai:
            ai = ask_gemini(
                sheet,
                audio,
                api_key,
                model
            )

            result["decision"] = ai["decision"]

            result["reason"] = str(
                ai.get(
                    "reason_th",
                    "AI ตรวจสอบแล้ว"
                )
            )[:400]

            result["issues"] = (
                ai.get("issues", [])
                if isinstance(
                    ai.get("issues"),
                    list
                )
                else []
            )

            result["video_type"] = str(
                ai.get(
                    "video_type",
                    result["video_type"]
                )
            )[:100]

        else:
            result["decision"] = "PASS"

            result["reason"] = (
                "ผ่านการตรวจเทคนิคเบื้องต้นเท่านั้น "
                "(ยังไม่ได้ตรวจมือ สินค้า "
                "และความต่อเนื่องด้วย Vision AI)"
            )

        result["notes"] = notes

        result["audio_present"] = bool(
            audio.get("present")
        )

        result["qualified"] = (
            use_ai or bool(issues)
        )

        result["elapsed"] = round(
            time.monotonic() - start,
            2
        )

        cache_put(
            key,
            result
        )

    except Exception as exc:
        result["reason"] = (
            f"ตรวจไม่สำเร็จ: {exc}"
        )

        result["elapsed"] = round(
            time.monotonic() - start,
            2
        )

        result["qualified"] = False

    return result
