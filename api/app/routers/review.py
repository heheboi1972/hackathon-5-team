# 역할: FR-005 돌아보기 — GET review, POST/DELETE notes (참조: API_SPEC §5) — 시여 담당 영역
# 스캐폴딩 스텁: 고정 저장형. 구간 지표·기준선 계산은 TODO
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_review 만 호출 (ISSUE B3).
# 지표는 {couple, mine} — 상대 값 미전송. 타입 고정은 ISSUE D4
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response, status

from ..deps import current_member
from ..models.api import NoteCreateRequest, NoteResponse, ReviewResponse, Who
from ..services.projection import build_review

router = APIRouter(prefix="/api/couples", tags=["review"])

KST = timezone(timedelta(hours=9))

# 구간 저장형 (사람별 a/b). 각 지표 dict 는 {couple, a, b}, 스칼라는 그대로 통과
_STORED = {
    "sessions": [
        {
            "session_id": 1187,
            "started_at": datetime(2026, 8, 19, 22, 10, tzinfo=KST),
            "ended_at": datetime(2026, 8, 19, 23, 55, tzinfo=KST),
            "initiator": "a",
            "msg_count": 34,
        }
    ],
    "metrics": {
        "range": {
            "question_rate": {"couple": 0.2, "a": 0.1, "b": 0.3},
            "message_length_median": {"couple": 13, "a": 9, "b": 20},
            "reply_gap_median_min": {"couple": 12, "a": 3, "b": 41},
            "session_length_median": 34,
        },
        "baseline": {
            "weeks": 8,
            "question_rate": {"couple": 0.23, "a": 0.22, "b": 0.24},
            "message_length_median": {"couple": 13, "a": 14, "b": 12},
            "reply_gap_median_min": {"couple": 5, "a": 4, "b": 6},
            "session_length_median": 22,
        },
    },
    "notes": [
        {
            "note_id": 7,
            "author": "a",
            "body": "시험 끝나고 싸움",
            "created_at": datetime(2026, 8, 20, 9, 0, tzinfo=KST),
        }
    ],
}


@router.get("/{couple_id}/review", response_model=ReviewResponse)
async def review(
    couple_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    session_id: int | None = None,
    me: Who = Depends(current_member),
) -> ReviewResponse:
    s = start or datetime(2026, 8, 17, 0, 0, tzinfo=KST)
    e = end or datetime(2026, 8, 21, 0, 0, tzinfo=KST)
    return build_review(_STORED, me, s, e)


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
