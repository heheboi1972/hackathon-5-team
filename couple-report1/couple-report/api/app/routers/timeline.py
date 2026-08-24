"""FR-003 타임라인 API Mock 라우터."""

from datetime import date

from fastapi import APIRouter, Query

from app.deps import CurrentMember
from app.models.api import TimelineResponse


router = APIRouter(prefix="/api/couples/{couple_id}", tags=["timeline"])


def mock_summary() -> dict[str, object]:
    return {
        "session_count": 18,
        "message_count": 412,
        "question_rate": {"couple": 0.20, "mine": 0.18},
        "message_length_median": {"couple": 12, "mine": 14},
        "reply_gap_median_min": {"couple": 5, "mine": 4},
        "resume_delay_median_min": {"couple": 118, "mine": 95},
        "session_length_median": 22,
        "activity": {
            "top_weekday": 2,
            "top_hour": 21,
            "by_weekday": [48, 55, 81, 60, 52, 70, 46],
            "by_hour": [0] * 21 + [12, 3, 1],
        },
        "sentiment": {"pos": [{"canonical": "좋아", "count": 5}], "neg": []},
    }


@router.get("/timeline", response_model=TimelineResponse)
async def timeline(
    couple_id: str,
    _: CurrentMember,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
) -> TimelineResponse:
    del couple_id, from_, to
    return TimelineResponse(
        weeks=[
            {
                "week_start": "2026-08-17",
                "in_progress": False,
                "report_status": "generated",
                "summary": mock_summary(),
                "outlier_count": 1,
                "events": [],
            }
        ]
    )

