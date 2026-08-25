"""FR-005 돌아보기 지표 계산.

DB 행을 저장형 ``{couple, a, b}``으로 계산할 뿐 응답 투영은 하지 않는다.
최종 ``{couple, mine}`` 변환과 모델 검증은 ``projection.build_review``의 책임이다.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any

from .metrics import BASELINE_WEEKS_TREND, band, week_start_of

BASELINE_MAX_WEEKS = 8
INSUFFICIENT_COMMENT = "아직 평소와 비교할 대화 기록이 충분하지 않아요."


def elapsed_days(start: datetime, end: datetime) -> float:
    """기존 start/end 경과 시간 의미를 유지한 일수. 양 끝 보정(+1)을 하지 않는다."""
    return max(0.0, (end - start).total_seconds() / 86_400)


def prorate_message_count(
    total: int,
    baseline_start: datetime,
    baseline_end: datetime,
    range_start: datetime,
    range_end: datetime,
) -> float | None:
    """baseline 일평균을 선택 날짜 범위 길이에 맞춰 환산한다."""
    baseline_days = elapsed_days(baseline_start, baseline_end)
    if total == 0 or baseline_days == 0:
        return None
    return round(total / baseline_days * elapsed_days(range_start, range_end), 1)


def average_session_message_count(sessions: list[dict[str, Any]]) -> float | None:
    if not sessions:
        return None
    return round(statistics.mean(int(item["msg_count"]) for item in sessions), 1)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def metric_snapshot(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """weekly metrics와 같은 풀링/중앙값 정의로 review 구간을 계산한다."""
    ordered = sorted(messages, key=lambda item: item["sent_at"])
    # 저장 스키마에는 msg_type이 없지만 비텍스트는 body_len=0으로 저장된다.
    # 기존 weekly question_rate와 같이 텍스트만 분모로 사용한다.
    text_messages = [item for item in ordered if item.get("body_len", 1) > 0]
    by_sender = {
        who: [item for item in text_messages if item["sender"] == who]
        for who in ("a", "b")
    }
    gaps: dict[str, list[float]] = defaultdict(list)
    couple_gaps: list[float] = []
    previous_by_session: dict[int, dict[str, Any]] = {}
    for item in ordered:
        session_id = item.get("session_id")
        if session_id is None:
            continue
        previous = previous_by_session.get(session_id)
        if previous is not None and previous["sender"] != item["sender"]:
            gap = (item["sent_at"] - previous["sent_at"]).total_seconds() / 60
            gaps[item["sender"]].append(gap)
            couple_gaps.append(gap)
        previous_by_session[session_id] = item

    return {
        "question_rate": {
            "couple": _ratio(sum(bool(item["is_question"]) for item in text_messages), len(text_messages)),
            "a": _ratio(sum(bool(item["is_question"]) for item in by_sender["a"]), len(by_sender["a"])),
            "b": _ratio(sum(bool(item["is_question"]) for item in by_sender["b"]), len(by_sender["b"])),
        },
        "reply_gap_median_min": {
            "couple": _median(couple_gaps),
            "a": _median(gaps["a"]),
            "b": _median(gaps["b"]),
        },
        "message_count": len(ordered),
    }


_COMMENT_TEXT = {
    ("reply_gap_median_min", "down", "slight"): "평소보다 답장이 조금 빨라졌어요.",
    ("reply_gap_median_min", "down", "clear"): "평소보다 답장이 뚜렷하게 빨라졌어요.",
    ("reply_gap_median_min", "up", "slight"): "평소보다 답장 간격이 조금 길어졌어요.",
    ("reply_gap_median_min", "up", "clear"): "평소보다 답장 간격이 뚜렷하게 길어졌어요.",
    ("question_rate", "up", "slight"): "평소보다 서로에게 묻는 순간이 조금 늘었어요.",
    ("question_rate", "up", "clear"): "평소보다 서로에게 묻는 순간이 뚜렷하게 늘었어요.",
    ("question_rate", "down", "slight"): "평소보다 서로에게 묻는 순간이 조금 줄었어요.",
    ("question_rate", "down", "clear"): "평소보다 서로에게 묻는 순간이 뚜렷하게 줄었어요.",
    ("message_count", "up", "slight"): "평소보다 대화를 조금 더 많이 나눴어요.",
    ("message_count", "up", "clear"): "평소보다 대화를 뚜렷하게 더 많이 나눴어요.",
    ("message_count", "down", "slight"): "평소보다 대화량이 조금 줄었어요.",
    ("message_count", "down", "clear"): "평소보다 대화량이 뚜렷하게 줄었어요.",
}


def review_comment(
    range_metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    *,
    comparable: bool,
) -> str:
    """couple 축만으로 한 문장의 결정론적 방향성을 만든다."""
    if not comparable:
        return INSUFFICIENT_COMMENT

    candidates: list[tuple[int, int, str, str, str]] = []
    for priority, metric in enumerate(
        ("reply_gap_median_min", "question_rate", "message_count")
    ):
        current = range_metrics[metric]
        baseline = baseline_metrics[metric]
        if isinstance(current, dict):
            current = current.get("couple")
        if isinstance(baseline, dict):
            baseline = baseline.get("couple")
        result = band(current, baseline)
        if result is None or result["direction"] == "steady":
            continue
        strength = 1 if result["magnitude"] == "clear" else 0
        candidates.append(
            (strength, -priority, metric, result["direction"], result["magnitude"])
        )

    if not candidates:
        return "평소와 비슷한 흐름으로 대화를 나눴어요."
    _, _, metric, direction, magnitude = max(candidates)
    return _COMMENT_TEXT[(metric, direction, magnitude)]


def build_stored_review(raw: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """repository 원시 행을 projection 입력 저장형으로 조립한다."""
    current = metric_snapshot(raw["messages"])
    historical = metric_snapshot(raw["baseline_messages"])
    weeks = min(
        BASELINE_MAX_WEEKS,
        len({week_start_of(item["sent_at"].date()) for item in raw["baseline_messages"]}),
    )
    if mode == "session":
        baseline_message_count = average_session_message_count(raw["baseline_sessions"])
    else:
        baseline_message_count = prorate_message_count(
            historical["message_count"],
            raw["baseline_start"],
            raw["range_start"],
            raw["range_start"],
            raw["range_end"],
        )
    baseline = {
        "weeks": weeks,
        "question_rate": historical["question_rate"],
        "reply_gap_median_min": historical["reply_gap_median_min"],
        "message_count": baseline_message_count,
    }
    comparable = weeks >= BASELINE_WEEKS_TREND and (
        mode != "session" or baseline_message_count is not None
    )
    comment = review_comment(
        current,
        baseline,
        comparable=comparable,
    )
    return {
        "sessions": raw["sessions"],
        "metrics": {"range": current, "baseline": baseline, "comment": comment},
        "notes": raw["notes"],
    }
