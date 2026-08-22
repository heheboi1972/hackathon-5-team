# 역할: FR-003 타임라인 — GET /api/couples/{id}/timeline (참조: API_SPEC §4.1)
# 스캐폴딩 스텁: 고정 3주 데이터. weekly_metrics 조회는 TODO(윤석)
from datetime import date

from fastapi import APIRouter

from ..models.api import ABFloat, TimelineResponse, TimelineWeek, WeekSummary

router = APIRouter(prefix="/api/couples", tags=["timeline"])


def _summary(msg: int) -> WeekSummary:
    return WeekSummary(
        session_count=18,
        message_count=msg,
        initiation_ratio=ABFloat(a=0.61, b=0.39),
        question_rate=ABFloat(a=0.18, b=0.22),
        message_length_median=ABFloat(a=14, b=11),
        reply_gap_median_min=ABFloat(a=4, b=6),
        resume_delay_median_min=ABFloat(a=95, b=140),
        session_length_median=22,
    )


@router.get("/{couple_id}/timeline", response_model=TimelineResponse)
async def timeline(
    couple_id: str,
    from_: date | None = None,
    to: date | None = None,
) -> TimelineResponse:
    return TimelineResponse(
        weeks=[
            TimelineWeek(week_start=date(2026, 8, 3), report_status="generated",
                         summary=_summary(388), outlier_count=1),
            TimelineWeek(week_start=date(2026, 8, 10), report_status="generated",
                         summary=_summary(455), outlier_count=0),
            TimelineWeek(week_start=date(2026, 8, 17), report_status="generated",
                         summary=_summary(412), outlier_count=2),
        ]
    )
