# 역할: FR-005 돌아보기 — GET review, POST/DELETE notes (참조: API_SPEC §5) — 시여 담당 영역
# 스캐폴딩 스텁: 고정 응답. 구간 지표·기준선 계산은 TODO
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response, status

from ..models.api import (
    NoteCreateRequest,
    NoteResponse,
    ReviewMetrics,
    ReviewRange,
    ReviewResponse,
    SessionInfo,
)

router = APIRouter(prefix="/api/couples", tags=["review"])

KST = timezone(timedelta(hours=9))


@router.get("/{couple_id}/review", response_model=ReviewResponse)
async def review(
    couple_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    session_id: int | None = None,
) -> ReviewResponse:
    s = start or datetime(2026, 8, 17, 0, 0, tzinfo=KST)
    e = end or datetime(2026, 8, 21, 0, 0, tzinfo=KST)
    return ReviewResponse(
        range=ReviewRange(start=s, end=e),
        sessions=[
            SessionInfo(
                session_id=1187,
                started_at=datetime(2026, 8, 19, 22, 10, tzinfo=KST),
                ended_at=datetime(2026, 8, 19, 23, 55, tzinfo=KST),
                initiator="a",
                msg_count=34,
            )
        ],
        metrics=ReviewMetrics(
            range={
                "initiation_ratio": {"a": 0.8},
                "question_rate": {"a": 0.1, "b": 0.3},
                "message_length_median": {"a": 9, "b": 20},
                "reply_gap_median_min": {"a": 3, "b": 41},
                "session_length_median": 34,
            },
            baseline={
                "weeks": 8,
                "initiation_ratio": {"a": 0.5},
                "question_rate": {"a": 0.22, "b": 0.24},
                "message_length_median": {"a": 14, "b": 12},
                "reply_gap_median_min": {"a": 4, "b": 6},
                "session_length_median": 22,
            },
        ),
        notes=[
            NoteResponse(
                note_id=7,
                author="a",
                body="시험 끝나고 싸움",
                created_at=datetime(2026, 8, 20, 9, 0, tzinfo=KST),
            )
        ],
    )


@router.post("/{couple_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(couple_id: str, body: NoteCreateRequest) -> NoteResponse:
    return NoteResponse(
        note_id=8,
        author="a",
        body=body.body,
        range_start=body.range_start,
        range_end=body.range_end,
        created_at=datetime.now(KST),
    )


@router.delete("/{couple_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(couple_id: str, note_id: int) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
