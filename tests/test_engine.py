
import sys
from pathlib import Path
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qc_engine import AIReport, decide, media_info, frames_quick, choose_motion_frames


def report(**kwargs):
    data = dict(scene='คนยืนพูดถือสินค้า', transcript='สวัสดีค่ะ', speech_detected=True,
                speech_clear=True, product_match='yes', summary='ปกติ',
                findings=[], confidence=.93)
    data.update(kwargs)
    return AIReport.model_validate(data)


def test_pass():
    assert decide(report(), {'has_audio': True}, 'TALK', .78)[0] == 'PASS'


def test_major_fail():
    r = report(findings=[dict(category='ภาพ', severity='major', second=4.2,
                              detail='นิ้วมือหลอมเข้ากับสินค้าที่วินาทีนี้', confidence=.95)])
    assert decide(r, {'has_audio': True}, 'AUTO', .78)[0] == 'FAIL'


def test_uncertain_review():
    r = report(findings=[dict(category='เสียง', severity='uncertain', second=3,
                              detail='ชื่อสินค้าไม่ชัดต้องตรวจซ้ำอีกครั้ง', confidence=.6)])
    assert decide(r, {'has_audio': True}, 'TALK', .78)[0] == 'REVIEW'


def test_no_speech_fail_when_required():
    assert decide(report(speech_detected=False), {'has_audio': False}, 'TALK', .78)[0] == 'FAIL'


def test_invalid_report():
    try:
        report(confidence=1.5)
    except ValidationError:
        return
    assert False, 'invalid report must fail validation'
