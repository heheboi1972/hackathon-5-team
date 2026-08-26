"""3-9A review 지표/baseline/comment 순수 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from zoneinfo import ZoneInfo

from app.services.projection import build_review
from app.services.review_metrics import (
    INSUFFICIENT_COMMENT,
    average_session_message_count,
    build_stored_review,
    prorate_message_count,
    review_comment,
    metric_snapshot,
)

KST = ZoneInfo("Asia/Seoul")


def _messages(start: datetime, weeks: int = 4) -> list[dict]:
    rows = []
    for index in range(weeks):
        at = start + timedelta(weeks=index)
        rows.extend([
            {"session_id": index + 1, "sender": "a", "sent_at": at, "is_question": False},
            {"session_id": index + 1, "sender": "b", "sent_at": at + timedelta(minutes=4), "is_question": True},
        ])
    return rows


def _raw() -> dict:
    range_start = datetime(2026, 8, 20, tzinfo=KST)
    baseline_messages = _messages(range_start - timedelta(days=28))
    return {
        "range_start": range_start,
        "range_end": range_start + timedelta(days=3),
        "baseline_start": range_start - timedelta(days=28),
        "sessions": [{
            "session_id": 99,
            "started_at": range_start,
            "ended_at": range_start + timedelta(minutes=10),
            "initiator": "a",
            "msg_count": 3,
        }],
        "messages": [
            {"session_id": 99, "sender": "a", "sent_at": range_start, "is_question": True},
            {"session_id": 99, "sender": "b", "sent_at": range_start + timedelta(minutes=2), "is_question": False},
            {"session_id": 99, "sender": "a", "sent_at": range_start + timedelta(minutes=9), "is_question": True},
        ],
        "baseline_messages": baseline_messages,
        "baseline_sessions": [{"msg_count": 8}, {"msg_count": 12}],
        "notes": [],
    }


def test_date_baseline_message_count_is_prorated_without_inclusive_day_adjustment():
    start = datetime(2026, 6, 1, tzinfo=KST)
    assert prorate_message_count(
        3920,
        start,
        start + timedelta(days=56),
        start + timedelta(days=56),
        start + timedelta(days=59),
    ) == 210.0


def test_session_baseline_message_count_is_average_of_past_sessions():
    assert average_session_message_count([{"msg_count": 8}, {"msg_count": 12}]) == 10.0
    assert average_session_message_count([]) is None


def test_question_rate_pools_text_only_but_message_count_includes_attachments():
    start = datetime(2026, 8, 20, tzinfo=KST)
    snapshot = metric_snapshot([
        {"session_id": 1, "sender": "a", "sent_at": start, "body_len": 5, "is_question": True},
        {"session_id": 1, "sender": "b", "sent_at": start + timedelta(minutes=1), "body_len": 5, "is_question": False},
        {"session_id": 1, "sender": "a", "sent_at": start + timedelta(minutes=2), "body_len": 0, "is_question": False},
    ])
    assert snapshot["question_rate"]["couple"] == 0.5
    assert snapshot["message_count"] == 3


def test_build_stored_review_uses_total_range_count_and_baseline_mode():
    raw = _raw()
    by_date = build_stored_review(raw, mode="date")
    by_session = build_stored_review(raw, mode="session")
    assert by_date["metrics"]["range"]["message_count"] == 3
    assert not isinstance(by_date["metrics"]["range"]["message_count"], dict)
    assert by_date["metrics"]["baseline"]["message_count"] == 0.9
    assert by_session["metrics"]["baseline"]["message_count"] == 10.0
    assert by_date["metrics"]["baseline"]["weeks"] == 4

    raw["baseline_sessions"] = []
    no_session_baseline = build_stored_review(raw, mode="session")
    assert no_session_baseline["metrics"]["baseline"]["message_count"] is None
    assert no_session_baseline["metrics"]["comment"] == INSUFFICIENT_COMMENT


def test_comment_is_deterministic_numberless_and_uses_couple_only():
    current = {
        "reply_gap_median_min": {"couple": 4.0, "a": 100.0, "b": 1.0},
        "question_rate": {"couple": 0.2, "a": 0.9, "b": 0.0},
        "message_count": 100,
    }
    baseline = {
        "reply_gap_median_min": {"couple": 10.0, "a": 1.0, "b": 100.0},
        "question_rate": {"couple": 0.2, "a": 0.1, "b": 0.8},
        "message_count": 100.0,
    }
    first = review_comment(current, baseline, comparable=True)
    current["reply_gap_median_min"]["a"] = 0.0
    current["reply_gap_median_min"]["b"] = 999.0
    second = review_comment(current, baseline, comparable=True)
    assert first == second == "평소보다 답장이 뚜렷하게 빨라졌어요."
    assert re.search(r"\d", first) is None
    assert first.count(".") == 1 and first.endswith(".")


def test_comment_selects_strongest_band_then_fixed_metric_priority():
    current = {
        "reply_gap_median_min": {"couple": 12.0},
        "question_rate": {"couple": 0.5},
        "message_count": 140,
    }
    baseline = {
        "reply_gap_median_min": {"couple": 10.0},
        "question_rate": {"couple": 0.3},
        "message_count": 100.0,
    }
    # question/message는 clear, 동일 강도에서는 question이 우선한다.
    assert review_comment(current, baseline, comparable=True) == (
        "평소보다 서로에게 묻는 순간이 뚜렷하게 늘었어요."
    )
    current["reply_gap_median_min"]["couple"] = 15.0
    assert review_comment(current, baseline, comparable=True) == (
        "평소보다 답장 간격이 뚜렷하게 길어졌어요."
    )
    assert review_comment(current, baseline, comparable=True) == review_comment(
        current, baseline, comparable=True
    )


def test_insufficient_baseline_keeps_shape_and_fixed_comment():
    raw = _raw()
    raw["baseline_messages"] = raw["baseline_messages"][:2]
    stored = build_stored_review(raw, mode="date")
    assert stored["metrics"]["comment"] == INSUFFICIENT_COMMENT
    assert set(stored["metrics"]["baseline"]) == {
        "weeks", "question_rate", "reply_gap_median_min", "message_count"
    }


def test_review_projection_keeps_only_couple_and_requester_axis():
    raw = _raw()
    stored = build_stored_review(raw, mode="date")
    a = build_review(stored, "a", raw["range_start"], raw["range_end"]).model_dump(mode="json")
    b = build_review(stored, "b", raw["range_start"], raw["range_end"]).model_dump(mode="json")
    for section in ("range", "baseline"):
        for metric in ("question_rate", "reply_gap_median_min"):
            assert a["metrics"][section][metric]["couple"] == b["metrics"][section][metric]["couple"]
            assert a["metrics"][section][metric]["mine"] != b["metrics"][section][metric]["mine"]
    encoded = json.dumps({"a_response": a, "b_response": b}, ensure_ascii=False)
    assert '"a":' not in encoded and '"b":' not in encoded
