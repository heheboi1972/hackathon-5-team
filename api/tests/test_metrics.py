# 역할: 지표 순수 함수 테스트 — 세션 ID 결정론(TC-METRIC-001), activity(TC-METRIC-006),
#       count_terms/top_terms(TC-METRIC-007), 커플 합산 정의(TC-METRIC-008)
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.kakao_parser import Message, tokenize
from app.services.metrics import (
    SESSION_GAP_MIN,
    TERM_MIN_COUNT,
    build_weekly_metrics,
    count_terms,
    split_sessions,
    top_terms,
)

KST = ZoneInfo("Asia/Seoul")


def _m(sender: str, when: str, body: str, is_question: bool = False) -> Message:
    return Message(
        sender=sender,
        sent_at=datetime.fromisoformat(when).replace(tzinfo=KST),
        body=body,
        msg_type="text",
        is_question=is_question,
        body_len=len(body),
        tokens=tokenize(body),
    )


def test_session_gap_29_minutes_stays_in_same_session():
    assert SESSION_GAP_MIN == 30
    messages = [
        _m("a", "2026-03-02 20:00", "안녕"),
        _m("b", "2026-03-02 20:29", "응"),
    ]

    sessions = split_sessions(messages)

    assert len(sessions) == 1
    assert sessions[0].msg_count == 2


def test_session_gap_exactly_30_minutes_starts_new_session():
    assert SESSION_GAP_MIN == 30
    messages = [
        _m("a", "2026-03-02 20:00", "안녕"),
        _m("b", "2026-03-02 20:30", "응"),
    ]

    sessions = split_sessions(messages)

    assert len(sessions) == 2
    assert [session.msg_count for session in sessions] == [1, 1]


def test_session_count_is_monotone_non_increasing_as_gap_grows():
    messages = [
        _m("a", "2026-03-02 20:00", "m0"),
        _m("b", "2026-03-02 20:10", "m1"),
        _m("a", "2026-03-02 20:30", "m2"),
        _m("b", "2026-03-02 21:10", "m3"),
        _m("a", "2026-03-02 22:20", "m4"),
    ]

    session15 = len(split_sessions(messages, gap_min=15))
    session30 = len(split_sessions(messages, gap_min=30))
    session60 = len(split_sessions(messages, gap_min=60))

    assert session15 >= session30 >= session60
    assert (session15, session30, session60) == (4, 3, 2)


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


# ---------------------------------------------------------------- TC-METRIC-008: 커플 합산 정의 (ISSUE B3)


def test_couple_question_rate_is_pooled_not_averaged():
    """couple 은 사람별 비율의 평균이 아니라 메시지를 합친 뒤의 비율."""
    msgs = [_m("a", f"2026-03-02 20:{i:02d}", "x", is_question=i < 3) for i in range(10)]   # A: 10중 3
    msgs += [_m("b", f"2026-03-02 21:{i:02d}", "x", is_question=True) for i in range(2)]    # B: 2중 2
    q = build_weekly_metrics(msgs, "a", "b")[0]["metrics"]["question_rate"]
    assert q["a"] == 0.3 and q["b"] == 1.0
    assert q["couple"] == round(5 / 12, 3)          # 0.417 — 평균(0.65) 이 아니다
    assert q["couple"] != round((0.3 + 1.0) / 2, 3)


def test_couple_message_length_median_is_pooled_distribution():
    """합친 분포의 중앙값 — 사람별 중앙값의 평균이 아니다."""
    msgs = [
        _m("a", "2026-03-02 20:00", "x" * 3),
        _m("a", "2026-03-02 20:01", "x" * 5),
        _m("b", "2026-03-02 20:02", "x" * 100),
    ]
    ml = build_weekly_metrics(msgs, "a", "b")[0]["metrics"]["message_length_median"]
    assert ml["a"] == 4 and ml["b"] == 100
    assert ml["couple"] == 5                        # median([3, 5, 100]) — 평균(52) 이 아니다


def test_couple_reply_gap_is_both_directions():
    msgs = [
        _m("a", "2026-03-02 20:00", "x"),
        _m("b", "2026-03-02 20:02", "x"),   # B 가 2분 만에 답
        _m("a", "2026-03-02 20:12", "x"),   # A 가 10분 만에 답
    ]
    rg = build_weekly_metrics(msgs, "a", "b")[0]["metrics"]["reply_gap_median_min"]   # 추이형으로 승격
    assert rg["a"] == 10.0 and rg["b"] == 2.0
    assert rg["couple"] == 6.0                      # median([2, 10])


def test_reply_gap_is_a_trend_metric_with_baseline():
    """A2 로 initiation_ratio 가 빠진 자리 — reply_gap 이 추이형으로 승격(baseline/delta 보유)."""
    week = build_weekly_metrics(
        [_m("a", "2026-03-02 20:00", "x"), _m("b", "2026-03-02 20:02", "x")], "a", "b"
    )[0]
    assert set(week["metrics"]) == {"question_rate", "message_length_median", "reply_gap_median_min"}
    rg = week["metrics"]["reply_gap_median_min"]
    assert "baseline_couple" in rg and "delta_couple" in rg
    # summary 는 metrics + summary_extras 로 조립되므로 중복 저장하지 않는다
    assert "reply_gap_median_min" not in week["summary_extras"]
    assert "resume_delay_median_min" in week["summary_extras"]


def test_comparable_is_decided_by_couple_axis():
    """4주 미만 → comparable=False, baseline/delta 는 세 축 모두 None."""
    msgs = [_m("a", "2026-03-02 20:00", "x"), _m("b", "2026-03-02 20:05", "x")]
    q = build_weekly_metrics(msgs, "a", "b")[0]["metrics"]["question_rate"]
    assert q["comparable"] is False
    for axis in ("couple", "a", "b"):
        assert q[f"baseline_{axis}"] is None and q[f"delta_{axis}"] is None
