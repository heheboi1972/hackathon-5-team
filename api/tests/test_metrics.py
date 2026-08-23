# 역할: 지표 순수 함수 테스트 — 세션 ID 결정론(TC-METRIC-001), activity(TC-METRIC-006), count_terms/top_terms(TC-METRIC-007)
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.kakao_parser import Message, tokenize
from app.services.metrics import (
    TERM_MIN_COUNT,
    build_weekly_metrics,
    count_terms,
    split_sessions,
    top_terms,
)

KST = ZoneInfo("Asia/Seoul")


def _m(sender: str, when: str, body: str) -> Message:
    return Message(
        sender=sender,
        sent_at=datetime.fromisoformat(when).replace(tzinfo=KST),
        body=body,
        msg_type="text",
        is_question=False,
        body_len=len(body),
        tokens=tokenize(body),
    )


def test_session_id_is_deterministic_epoch_of_start():
    msgs = [
        _m("a", "2026-03-02 20:00", "안녕"),
        _m("b", "2026-03-02 20:05", "응"),
        _m("a", "2026-03-03 09:00", "좋은 아침"),   # 30분 넘게 끊김 → 새 세션
    ]
    s1 = split_sessions(msgs)
    s2 = split_sessions(list(reversed(msgs)))         # 입력 순서가 달라도
    assert [s.session_id for s in s1] == [s.session_id for s in s2]
    assert s1[0].session_id == int(msgs[0].sent_at.timestamp())
    assert len(s1) == 2


def test_activity_top_weekday_and_hour():
    msgs = [
        _m("a", "2026-03-04 21:10", "x"),   # 수(2) 21시
        _m("b", "2026-03-04 21:20", "x"),
        _m("a", "2026-03-05 09:00", "x"),   # 목(3) 09시
    ]
    week = build_weekly_metrics(msgs, "a", "b")[0]
    act = week["summary_extras"]["activity"]
    assert act["top_weekday"] == 2 and act["top_hour"] == 21
    assert sum(act["by_weekday"]) == 3 and act["by_hour"][21] == 2
    assert "initiation_ratio" not in week["metrics"]


LEX = {"좋아": ("좋아", "pos"), "조아": ("좋아", "pos"), "짜증": ("짜증", "neg"), "응": ("응", "neutral")}


def test_count_terms_merges_canonical_and_excludes_negated():
    msgs = [
        _m("a", "2026-03-02 20:00", "오늘 진짜 좋아"),
        _m("a", "2026-03-02 20:01", "조아조아"),        # 반복 → "조아" → canonical 좋아
        _m("a", "2026-03-02 20:02", "안 좋아"),         # 부정어 → 제외
        _m("a", "2026-03-02 20:03", "좋아하지 않아"),   # 뒤 "지않" → 제외
        _m("b", "2026-03-02 20:04", "짜증이 나"),       # 조사 제거 → 짜증
        _m("b", "2026-03-02 20:05", "응"),              # neutral → 안 셈
    ]
    c = count_terms(msgs, LEX)
    assert c[("a", "좋아", "pos")] == 2
    assert c[("b", "짜증", "neg")] == 1
    assert ("b", "응", "neutral") not in c


def test_top_terms_hides_below_min_count_and_is_per_person():
    counts = {("a", "좋아", "pos"): 5, ("a", "고마워", "pos"): TERM_MIN_COUNT - 1, ("b", "짜증", "neg"): 4}
    mine = top_terms(counts, "a")
    assert mine == {"pos": [{"canonical": "좋아", "count": 5}], "neg": []}
    assert top_terms(counts, "b")["neg"][0]["canonical"] == "짜증"
