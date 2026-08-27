"""
저장형 → 응답형 변환 (ISSUE B3, B1).

`weekly_metrics.summary`·`reports.report` 는 커플당 한 행이라 사람별(a/b) 값을 그대로 담는다.
응답은 **커플 값 + 요청자 본인 값(mine)** 만 내보낸다 — 상대 값은 표시를 안 하는 수준이 아니라
아예 전송하지 않는다 (P-3 예외). `weekly_terms`(양쪽 저장 → 응답만 필터)와 같은 구조.

역산 방지: 노출되는 값이 전부 중앙값·풀링 비율이고 응답에 사람별 메시지 수가 없으므로
`couple` 과 `mine` 으로 상대 값을 되돌릴 수 없다.

**라우터 규칙**: 라우터는 응답 모델을 직접 만들지 않는다. `build_timeline`·`build_report`·
`build_review` 만 호출한다. 투영이 조립 함수 안쪽에 있어야 읽기 경로마다 빠뜨리는 일이 없다.
우회해서 직접 모델을 만들면 `CoupleMine.mine`·`MetricComparison.mine` 이 필수라 즉시 터진다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..models.api import (
    ReportResponse,
    ReviewResponse,
    TimelineResponse,
    Who,
)

# summary 안에서 {couple, a, b} 형태를 갖는 키들
PER_PERSON_SUMMARY_KEYS = (
    "question_rate",
    "message_length_median",
    "reply_gap_median_min",
    "resume_delay_median_min",
)


# ---------------------------------------------------------------- 필드 단위 투영


def _pick(stored: dict[str, Any], me: Who) -> dict[str, Any]:
    """{couple, a, b, baseline_*, delta_*} → {couple, mine, baseline_couple, baseline_mine, ...}"""
    out: dict[str, Any] = {"couple": stored.get("couple"), "mine": stored.get(me)}
    for prefix in ("baseline", "delta"):
        if f"{prefix}_couple" in stored or f"{prefix}_{me}" in stored:
            out[f"{prefix}_couple"] = stored.get(f"{prefix}_couple")
            out[f"{prefix}_mine"] = stored.get(f"{prefix}_{me}")
    if "comparable" in stored:
        out["comparable"] = stored["comparable"]
    return out


def project_summary(stored: dict[str, Any], me: Who, my_terms: dict | None = None) -> dict[str, Any]:
    """WeekSummary 투영. `my_terms` 는 요청자 본인의 top_terms 결과(없으면 null — 사전 미구축)."""
    out = dict(stored)
    for key in PER_PERSON_SUMMARY_KEYS:
        if isinstance(out.get(key), dict):
            out[key] = _pick(out[key], me)
    out["sentiment"] = my_terms
    return out


def project_metrics(stored: dict[str, Any], me: Who) -> dict[str, Any]:
    """지표 맵 투영. dict 가 아닌 값(`session_length_median`, `weeks` 등)은 그대로 통과."""
    return {k: (_pick(v, me) if isinstance(v, dict) else v) for k, v in stored.items()}


def strip_who(outliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """moments 조립용. 이상치 **판정**은 사람별 분포로 계속하고(정확도), 응답에서 `who` 만 뺀다."""
    return [{k: v for k, v in o.items() if k != "who"} for o in outliers]


# ---------------------------------------------------------------- 응답 조립 (라우터가 부르는 것)


def build_timeline(
    stored_weeks: list[dict[str, Any]],
    me: Who,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> TimelineResponse:
    """주차별 저장형 → 타임라인 응답.

    범위 양 끝은 포함하며, 저장 순서와 무관하게 월요일 오름차순으로 반환한다.
    `weekly_terms` 는 {a, b} 로 들고 있고 요청자 것만 나간다.
    """
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    current_week = today - timedelta(days=today.weekday())
    selected: list[tuple[date, dict[str, Any]]] = []
    for stored in stored_weeks:
        week_start = stored["week_start"]
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start)
        if week_start.weekday() != 0:
            raise ValueError(f"week_start는 월요일이어야 합니다: {week_start}")
        if from_ is not None and week_start < from_:
            continue
        if to is not None and week_start > to:
            continue
        selected.append((week_start, stored))

    return TimelineResponse.model_validate({
        "weeks": [
            {
                "week_start": week_start,
                "in_progress": week_start == current_week,
                "report_status": w.get("report_status", "pending"),
                "summary": project_summary(w["summary"], me, w.get("weekly_terms", {}).get(me)),
                "outlier_count": w.get("outlier_count", 0),
                "events": w.get("events", []),
            }
            for week_start, w in sorted(selected, key=lambda item: item[0])
        ]
    })


def build_report(stored: dict[str, Any], me: Who, week_start: date) -> ReportResponse:
    """저장형 리포트 → 요청자용 응답."""
    return ReportResponse.model_validate({
        "week_start": week_start.isoformat(),
        "status": stored["status"],
        "summary": project_summary(stored["summary"], me, stored.get("weekly_terms", {}).get(me)),
        "metrics": project_metrics(stored["metrics"], me),
        "highlights": stored["highlights"],
        "suggestions": stored["suggestions"],
        "moments": strip_who(stored["moments"]),
        "safety": stored["safety"],
    })


def build_review(stored: dict[str, Any], me: Who, start: datetime, end: datetime) -> ReviewResponse:
    """구간 저장형 → 돌아보기 응답.

    지표는 question_rate·reply_gap_median_min(CoupleMine) + message_count(구간 합산, 개인별
    미제공) 3개로 한정한다 — message_length_median·session_length_median 은 응답에서 뺀다
    (카드에 안 보여주기로 결정, 2026-08-25). `comment`는 이미 `services/review_metrics.py`의
    `review_comment()`가 숫자 없이 방향만 코드로 생성해서 `stored`에 담아 넘겨준다(LLM 미사용 —
    B4를 재현성 있게 보장하기 위함) — 여기서는 그대로 통과시키기만 한다(윤아+윤석 병합, 2026-08-25).
    """
    sessions = [
        {**session, "initiated_by_me": session["initiator"] == me}
        for session in stored["sessions"]
    ]
    return ReviewResponse.model_validate({
        "range": {"start": start, "end": end},
        "sessions": sessions,
        "metrics": {
            "range": project_metrics(stored["metrics"]["range"], me),
            "baseline": project_metrics(stored["metrics"]["baseline"], me),
            "comment": stored["metrics"]["comment"],
        },
        "notes": stored["notes"],
    })
