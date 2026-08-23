# 역할: FR-003 타임라인 — GET /api/couples/{id}/timeline (참조: API_SPEC §4.1)
# 스캐폴딩 스텁: 고정 3주 데이터. weekly_metrics 조회는 TODO(윤석)
# TODO(윤석): summary.sentiment 는 요청자(me) 의 weekly_terms 만 채움 — 상대 데이터 미전송 (P-3 예외, ISSUE B1)
from datetime import date

from fastapi import APIRouter

from ..models.api import ABFloat, Activity, MyTerms, TermCount, TimelineResponse, TimelineWeek, WeekSummary

router = APIRouter(prefix="/api/couples", tags=["timeline"])


def _summary(msg: int) -> WeekSummary:
    return WeekSummary(
        session_count=18,
        message_count=msg,
        question_rate=ABFloat(a=0.18, b=0.22),
        message_length_median=ABFloat(a=14, b=11),
        reply_gap_median_min=ABFloat(a=4, b=6),
        resume_delay_median_min=ABFloat(a=95, b=140),
        session_length_median=22,
        activity=Activity(top_weekday=2, top_hour=21,
                          by_weekday=[48, 55, 81, 60, 52, 70, 46],
                          by_hour=[2,1,0,0,0,0,1,6,14,18,15,12,20,16,14,17,19,22,28,34,41,46,30,16]),
        sentiment=MyTerms(pos=[TermCount(canonical="좋아", count=41), TermCount(canonical="고마워", count=12)],
                          neg=[TermCount(canonical="피곤해", count=7)]),
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
