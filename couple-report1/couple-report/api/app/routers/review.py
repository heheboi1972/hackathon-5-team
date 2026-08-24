"""FR-005 구간 돌아보기 및 메모 API Mock 라우터."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response, status

from app.deps import CurrentMember
from app.models.api import NoteCreateRequest, NoteResponse, ReviewResponse


router = APIRouter(prefix="/api/couples/{couple_id}", tags=["review"])


@router.get("/review", response_model=ReviewResponse)
async def review(
    couple_id: str,
    member: CurrentMember,
    start: datetime | None = None,
    end: datetime | None = None,
    session_id: int | None = None,
) -> ReviewResponse:
    del couple_id, member, session_id
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(days=1)
    return ReviewResponse(
        range={"start": start, "end": end},
        sessions=[],
        metrics={
            "range": {"question_rate": {"couple": 0.2, "mine": 0.1}},
            "baseline": {"weeks": 4, "question_rate": {"couple": 0.23, "mine": 0.22}},
        },
        notes=[],
    )


@router.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(couple_id: str, payload: NoteCreateRequest, member: CurrentMember) -> NoteResponse:
    del couple_id
    return NoteResponse(
        note_id=1,
        author=member,
        body=payload.body,
        range_start=payload.range_start,
        range_end=payload.range_end,
        created_at=datetime.now(timezone.utc),
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(couple_id: str, note_id: int, _: CurrentMember) -> Response:
    del couple_id, note_id
    return Response(status_code=status.HTTP_204_NO_CONTENT)

