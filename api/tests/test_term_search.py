# 역할: 단어 횟수 검색 순수 함수 테스트 (TC-API-008 term_count 근거)
from datetime import date

import pytest

from app.services.kakao_parser import tokenize
from app.services.term_search import (
    count_in_messages,
    format_answer,
    match_tokens,
    normalize_query,
)

LEX = {"좋아": ("좋아", "pos"), "조아": ("좋아", "pos"), "좋앙": ("좋아", "pos")}


@pytest.mark.parametrize("q,expected", [
    ("사랑해", "사랑해"),
    ("'짜증이'", "짜증"),      # 따옴표·조사 제거
    ("ㅋㅋㅋ", None),           # 자모만 → 토큰 없음
])
def test_normalize_query(q, expected):
    assert normalize_query(q) == expected


def test_match_exact_and_prefix():
    toks = tokenize("사랑해 사랑해요 사랑 미워")
    assert toks == ["사랑해", "사랑해", "사랑", "미워"]              # "사랑해요" 는 조사 제거로 이미 합쳐짐
    assert match_tokens(toks, "사랑해") == ["사랑해", "사랑해"]      # 완전일치
    assert len(match_tokens(toks, "사랑")) == 3                      # 접두: 사랑해·사랑해·사랑


def test_match_canonical_variants():
    toks = tokenize("조아 좋앙 미워")
    assert sorted(match_tokens(toks, "좋아", LEX)) == ["조아", "좋앙"]
    assert match_tokens(toks, "좋아") == []      # 사전 없으면 변형 매칭 안 됨


def test_count_is_couple_total_without_sender():
    msgs = [
        (date(2026, 3, 2), tokenize("사랑해 사랑해")),
        (date(2026, 3, 2), tokenize("나도 사랑행")),
        (date(2026, 3, 9), tokenize("사랑해")),
        (date(2026, 3, 9), tokenize("치킨 먹자")),
    ]
    r = count_in_messages(msgs, "사랑해")
    assert r["total"] == 3                                    # "사랑행" 은 접두가 아니라 사전 없이는 안 합쳐짐
    assert r["by_week"] == [
        {"week_start": date(2026, 3, 2), "count": 2},
        {"week_start": date(2026, 3, 9), "count": 1},
    ]
    assert "sender" not in r and all("sender" not in f for f in r["matched_forms"])

    # 시드 사전에 "사랑행 → 사랑해" 가 있으면 변형까지 합산된다
    lex = {"사랑해": ("사랑해", "pos"), "사랑행": ("사랑해", "pos")}
    r2 = count_in_messages(msgs, "사랑해", lex)
    assert r2["total"] == 4
    assert {f["form"] for f in r2["matched_forms"]} == {"사랑해", "사랑행"}


def test_count_arbitrary_non_sentiment_word():
    msgs = [(date(2026, 3, 2), tokenize("치킨 시킬까")), (date(2026, 3, 9), tokenize("치킨이 최고"))]
    assert count_in_messages(msgs, "치킨")["total"] == 2       # 감성 사전과 무관


def test_format_answer():
    r = count_in_messages([(date(2026, 3, 2), tokenize("좋아 조아"))], "좋아", LEX)
    assert "2번" in format_answer(r)
    assert "알려드리지 않아요" in format_answer(r, asked_about_person=True)
    zero = count_in_messages([], "없는말")
    assert "찾지 못했어요" in format_answer(zero)
