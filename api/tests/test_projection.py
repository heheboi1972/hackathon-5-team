# 역할: 저장형 → 응답형 투영 테스트 — 상대 값 미전송 계약 (ISSUE B3, TC-API-005-x)
from datetime import date, timedelta

import pytest

from app.services.projection import build_timeline, project_metrics, project_summary, strip_who

STORED_SUMMARY = {
    "session_count": 18,
    "message_count": 412,
    "question_rate": {"couple": 0.20, "a": 0.18, "b": 0.22},
    "message_length_median": {"couple": 12, "a": 14, "b": 11},
    "reply_gap_median_min": {"couple": 5, "a": 4, "b": 6},
    "resume_delay_median_min": {"couple": 118, "a": 95, "b": 140},
    "session_length_median": 22,
    "activity": {"top_weekday": 2, "top_hour": 21, "by_weekday": [0] * 7, "by_hour": [0] * 24},
}

STORED_METRICS = {
    "question_rate": {
        "couple": 0.20, "a": 0.18, "b": 0.22,
        "baseline_couple": 0.245, "baseline_a": 0.25, "baseline_b": 0.24,
        "delta_couple": -0.045, "delta_a": -0.07, "delta_b": -0.02,
        "comparable": True,
    }
}

PER_PERSON_KEYS = ("question_rate", "message_length_median", "reply_gap_median_min", "resume_delay_median_min")


def test_summary_projection_keeps_couple_and_own_value_only():
    a = project_summary(STORED_SUMMARY, "a", my_terms=None)
    b = project_summary(STORED_SUMMARY, "b", my_terms=None)
    assert a["question_rate"] == {"couple": 0.20, "mine": 0.18}
    assert b["question_rate"] == {"couple": 0.20, "mine": 0.22}
    for key in PER_PERSON_KEYS:
        # 상대 값은 표시를 안 하는 것이 아니라 응답에 담기지 않는다 (P-3 예외)
        assert "a" not in a[key] and "b" not in a[key]
        assert "a" not in b[key] and "b" not in b[key]
        # 커플 값은 두 사람에게 동일
        assert a[key]["couple"] == b[key]["couple"]


def test_summary_projection_carries_own_terms_only():
    mine = {"pos": [{"canonical": "좋아", "count": 41}], "neg": []}
    assert project_summary(STORED_SUMMARY, "a", mine)["sentiment"] == mine
    assert project_summary(STORED_SUMMARY, "a", None)["sentiment"] is None   # 사전 미구축


def test_metrics_projection_maps_baseline_and_delta():
    a = project_metrics(STORED_METRICS, "a")["question_rate"]
    b = project_metrics(STORED_METRICS, "b")["question_rate"]
    assert a == {
        "couple": 0.20, "mine": 0.18,
        "baseline_couple": 0.245, "baseline_mine": 0.25,
        "delta_couple": -0.045, "delta_mine": -0.07,
        "comparable": True,
    }
    assert b["mine"] == 0.22 and b["delta_mine"] == -0.02
    assert a["couple"] == b["couple"] and a["delta_couple"] == b["delta_couple"]
    for key in ("a", "b", "baseline_a", "baseline_b", "delta_a", "delta_b"):
        assert key not in a and key not in b


def test_strip_who_drops_speaker_but_keeps_judgement_inputs():
    """이상치 판정은 사람별 분포로 계속하고(정확도), 응답에서 who 만 뻐다."""
    stored = [{"metric": "reply_gap", "who": "b", "session_id": 1187, "value_min": 184,
               "baseline_median_min": 5, "direction": "high"}]
    out = strip_who(stored)
    assert "who" not in out[0]
    assert out[0]["value_min"] == 184 and out[0]["direction"] == "high"
    assert stored[0]["who"] == "b"   # 원본(weekly_metrics.outliers)은 그대로


def _timeline_week(week_start: date, report_status: str | None = "generated") -> dict:
    stored = {
        "week_start": week_start,
        "summary": STORED_SUMMARY,
        "weekly_terms": {
            "a": {"pos": [{"canonical": "좋아", "count": 5}], "neg": []},
            "b": {"pos": [{"canonical": "고마워", "count": 4}], "neg": []},
        },
        "outlier_count": 1,
        "events": [],
    }
    if report_status is not None:
        stored["report_status"] = report_status
    return stored


def test_timeline_projection_sorts_and_filters_inclusive_range():
    stored = [
        _timeline_week(date(2026, 8, 17)),
        _timeline_week(date(2026, 8, 3)),
        _timeline_week(date(2026, 8, 10)),
    ]

    response = build_timeline(
        stored,
        "a",
        from_=date(2026, 8, 10),
        to=date(2026, 8, 17),
    )

    assert [week.week_start for week in response.weeks] == [
        date(2026, 8, 10),
        date(2026, 8, 17),
    ]
    assert all(week.week_start.weekday() == 0 for week in response.weeks)


def test_timeline_projection_defaults_current_week_and_missing_report_to_pending():
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())

    week = build_timeline(
        [_timeline_week(current_monday, report_status=None)], "a"
    ).weeks[0]

    assert week.in_progress is True
    assert week.report_status == "pending"


def test_timeline_projection_rejects_non_monday_week_start():
    with pytest.raises(ValueError, match="월요일"):
        build_timeline([_timeline_week(date(2026, 8, 18))], "a")


def test_timeline_projection_keeps_couple_same_and_mine_requester_specific():
    stored = [_timeline_week(date(2026, 8, 17))]

    a = build_timeline(stored, "a").model_dump(mode="json")
    b = build_timeline(stored, "b").model_dump(mode="json")

    for key in PER_PERSON_KEYS:
        av = a["weeks"][0]["summary"][key]
        bv = b["weeks"][0]["summary"][key]
        assert av["couple"] == bv["couple"]
        assert av["mine"] != bv["mine"]
        assert not {"a", "b"} & set(av)
        assert not {"a", "b"} & set(bv)
    assert a["weeks"][0]["summary"]["sentiment"] != b["weeks"][0]["summary"]["sentiment"]
    assert a["weeks"][0]["summary"]["activity"] == b["weeks"][0]["summary"]["activity"]
