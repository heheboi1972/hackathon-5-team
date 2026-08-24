# 역할: 파서 테스트 — is_question (TC-PARSE-004), tokenize (TC-METRIC-007),
#       형식 감지·픽스처 파싱 (TC-PARSE-001~003)
from pathlib import Path

import pytest

from app.services.kakao_parser import (
    detect_format,
    is_question,
    parse_export,
    tokenize,
    validate_couple,
)

QUESTION_CASES = [
    ("뭐해?", True),
    ("뭐해?ㅋㅋ", True),
    ("뭐해", True),
    ("어디야ㅋㅋ", True),
    ("언제 와", True),
    ("몇 시야", True),
    ("왜", True),
    ("뭐 먹을까요", True),
    ("밥 먹었니", True),
    ("갈까ㅋㅋ", True),
    ("아니", False),
    ("집에 가요", False),
    ("할까 말까", False),
    ("언제 와!", False),
    ("알았어", False),
    ("그래야지", False),
    ("괜찮아", False),          # 동형 — 한계로 문서화
    ("진짜 미쳤다", False),
]


@pytest.mark.parametrize("body,expected", QUESTION_CASES)
def test_is_question(body, expected):
    assert is_question(body) is expected


TOKEN_CASES = [
    ("좋아아아아 ㅋㅋㅋ", ["좋아"]),
    ("오늘 짜증이 나네", ["오늘", "짜증", "나네"]),
    ("https://x.y 진짜!!! 피곤해요 12시", ["진짜", "피곤해", "12시"]),
]


@pytest.mark.parametrize("body,expected", TOKEN_CASES)
def test_tokenize(body, expected):
    assert tokenize(body) == expected

# ---------------------------------------------------------------- 픽스처 기반 (TC-PARSE-001~003)

FIXTURES = Path(__file__).parent / "fixtures" / "kakao"


def _load(name: str):
    return parse_export((FIXTURES / name).read_bytes())


@pytest.mark.parametrize(
    "name,fmt",
    [("pc.txt", "pc"), ("ios.txt", "ios"), ("android.txt", "android"), ("android_new.txt", "pc")],
)
def test_detect_format(name, fmt):
    # android_new 는 PC 와 형식이 같아 "pc" 로 감지된다 — 같은 파서를 쓰므로 결과는 동일
    text = (FIXTURES / name).read_bytes().decode("utf-8-sig")
    assert detect_format(text) == fmt


@pytest.mark.parametrize("name", ["pc.txt", "ios.txt", "android.txt"])
def test_fixture_parses_to_same_conversation(name):
    msgs = _load(name)
    assert len(msgs) == 176
    assert validate_couple(msgs) == ("김철수", "이영희")


def test_detect_format_rejects_unknown():
    with pytest.raises(ValueError):
        detect_format("그냥 아무 텍스트\n두 번째 줄")


# --- Android 최신 앱: 대괄호 형식 + 내부 줄바꿈도 CRLF (실제 샘플로 확인) ---

def test_android_new_message_count():
    msgs = _load("android_new.txt")
    assert len(msgs) == 6
    assert validate_couple(msgs) == ("김철수", "이영희")


def test_android_new_multiline_body_preserved():
    """내부 줄바꿈이 CRLF 라 레코드가 쪼개져도 한 Message 로 복원돼야 한다."""
    msgs = _load("android_new.txt")
    long_msg = max(msgs, key=lambda m: m.body_len)
    assert long_msg.body == "첫째 줄이야\n둘째 줄이고\n\n넷째 줄"
    assert long_msg.sender == "이영희"
    assert long_msg.sent_at.hour == 18


def test_android_new_excludes_system_messages():
    bodies = [m.body for m in _load("android_new.txt")]
    assert not any("초대했습니다" in b or "나갔습니다" in b or "방장이" in b for b in bodies)


def test_android_new_ampm_and_date_separator():
    msgs = _load("android_new.txt")
    by_time = {(m.sent_at.month, m.sent_at.day, m.sent_at.hour, m.sent_at.minute) for m in msgs}
    assert (8, 22, 12, 3) in by_time      # 오후 12:03 → 12:03
    assert (8, 23, 0, 10) in by_time      # 오전 12:10 → 다음 구분선 날짜의 00:10


def test_android_new_placeholder_types():
    types = {m.msg_type for m in _load("android_new.txt")}
    assert {"photo", "emoticon", "text"} <= types

def test_android_new_fixture_keeps_crlf_inside_message():
    """
    이 픽스처의 값어치는 '메시지 내부 줄바꿈도 CRLF' 라는 점에 있다.
    autocrlf 등으로 LF 정규화되면 회귀 테스트가 조용히 무의미해지므로 바이트로 못박는다.
    (.gitattributes 의 `-text` 와 한 쌍)
    """
    raw = (FIXTURES / "android_new.txt").read_bytes()
    assert raw.count(b"\r\n") > 0
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0
    # 여러 줄 메시지의 이어지는 줄이 CRLF 로 끊겨 있어야 버그가 재현된다
    assert "첫째 줄이야\r\n둘째 줄이고" in raw.decode("utf-8")
