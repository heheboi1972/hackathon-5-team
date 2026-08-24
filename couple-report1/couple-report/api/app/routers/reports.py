"""FR-004 주간 리포트 API Mock 라우터."""

from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, status

from app.deps import CurrentMember
from app.models.api import JobAcceptedResponse, ReportResponse
from app.routers.timeline import mock_summary


router = APIRouter(prefix="/api/couples/{couple_id}/reports", tags=["reports"])


@router.get("/{week_start}", response_model=ReportResponse)
async def get_report(couple_id: str, week_start: date, _: CurrentMember) -> ReportResponse:
    del couple_id
    return ReportResponse(
        week_start=week_start,
        status="generated",
        summary=mock_summary(),
        metrics={
            "question_rate": {
                "couple": 0.20,
                "mine": 0.18,
                "baseline_couple": 0.245,
                "baseline_mine": 0.25,
                "delta_couple": -0.045,
                "delta_mine": -0.07,
                "comparable": True,
            }
        },
        highlights=[
            {
                "id": "h1",
                "metric": "question_rate",
                "observation": "지난 몇 주보다 서로에게 묻는 순간이 조금 달라졌어요.",
                "interpretations": ["바쁜 시기였을 수도", "대화 주제가 일상 공유로 옮겨갔을 수도"],
                "evidence": [],
                "sources": [],
                "sentiment": "neutral",
            }
        ],
        suggestions=[
            {
                "id": "s1",
                "linked_highlight": "h1",
                "template_id": "q_rate_down_01",
                "text": "다음 대화에서 서로의 하루를 한 번 더 물어보면 어떨까요.",
            }
        ],
        moments=[
            {
                "kind": "reply_gap_high",
                "at": datetime(2026, 8, 19, 23, 41, tzinfo=timezone.utc).isoformat(),
                "session_id": 1187,
                "value_min": 184,
                "baseline_median_min": 5,
                "text": "평소보다 답장이 길어진 순간이 있었어요.",
            }
        ],
        safety={"passed": True, "rewritten": []},
    )


@router.post(
    "/{week_start}/regenerate",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_report(
    couple_id: str, week_start: date, _: CurrentMember
) -> JobAcceptedResponse:
    del couple_id, week_start
    return JobAcceptedResponse(job_id=str(uuid4()))

