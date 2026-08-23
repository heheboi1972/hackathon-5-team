# 역할: 파서 순수 함수 테스트 — is_question (TC-PARSE-004), tokenize (TC-METRIC-007)
import pytest

from app.services.kakao_parser import is_question, tokenize

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
