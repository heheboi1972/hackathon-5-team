# 역할: FR-003 타임라인 — GET /api/couples/{id}/timeline (참조: API_SPEC §4.1)
# 스캐폴딩 스텁: 고정 3주 저장형 데이터. weekly_metrics 조회는 TODO(윤석)
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_timeline 만 호출 (ISSUE B3).
# TODO(윤석): _STORED_WEEKS 를 weekly_metrics + weekly_terms 조회로 교체. build_timeline 은 그대로 두면 된다.
from datetime import date

from fastapi import APIRouter, Depends

from ..deps import current_member
from ..models.api import TimelineResponse, Who
from ..services.projection import build_timeline

router = APIRouter(prefix="/api/couples", tags=["timeline"])

_ACTIVITY = {
    "top_weekday": 2, "top_hour": 21,
    "by_weekday": [48, 55, 81, 60, 52, 70, 46],
    "by_hour": [2, 1, 0, 0, 0, 0, 1, 6, 14, 18, 15, 12, 20, 16, 14, 17, 19, 22, 28, 34, 41, 46, 30, 16],
}

# weekly_terms 는 양쪽 저장, 응답은 요청자 것만 (ISSUE B1)
_TERMS = {
    "a": {"pos": [{"canonical": "좋아", "count": 41}, {"canonical": "고마워", "count": 12}],
          "neg": [{"canonical": "피곤해", "count": 7}]},
    "b": {"pos": [{"canonical": "귀여워", "count": 15}], "neg": [{"canonical": "바쁘", "count": 5}]},
}


def _stored(week: date, msg: int, outliers: int, q: tuple, ml: tuple, rg: tuple, rd: tuple) -> dict:
    """weekly_metrics 한 행의 저장형 (사람별 a/b). 각 튜플 = (couple, a, b)"""
    def ab(t):
        return {"couple": t[0], "a": t[1], "b": t[2]}
    return {
        "week_start": week,
        "report_status": "generated",
        "outlier_count": outliers,
        "summary": {
            "session_count": 18,
            "message_count": msg,
            "question_rate": ab(q),
            "message_length_median": ab(ml),
            "reply_gap_median_min": ab(rg),
            "resume_delay_median_min": ab(rd),
            "session_length_median": 22,
            "activity": _ACTIVITY,
        },
        "weekly_terms": _TERMS,
    }


_STORED_WEEKS = [
    _stored(date(2026, 8, 3), 388, 1, (0.23, 0.21, 0.25), (13, 15, 12), (4, 3, 5), (105, 88, 122)),
    _stored(date(2026, 8, 10), 455, 0, (0.21, 0.19, 0.23), (12, 14, 11), (5, 4, 6), (112, 92, 132)),
    _stored(date(2026, 8, 17), 412, 2, (0.20, 0.18, 0.22), (12, 14, 11), (5, 4, 6), (118, 95, 140)),
]


@router.get("/{couple_id}/timeline", response_model=TimelineResponse)
async def timeline(
    couple_id: str,
    from_: date | None = None,
    to: date | None = None,
    me: Who = Depends(current_member),
) -> TimelineResponse:
    return build_timeline(_STORED_WEEKS, me)
