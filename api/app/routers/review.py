# 역할: FR-005 돌아보기 — GET review, POST/DELETE notes (참조: API_SPEC §5) — 시여 담당 영역
# 스캐폴딩 스텁: 고정 저장형. 구간 지표·기준선 계산은 TODO
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_review 만 호출 (ISSUE B3).
# 지표는 {couple, mine} — 상대 값 미전송. 타입 고정은 ISSUE D4
#
# 2026-08-25: metrics.range/baseline 을 question_rate·reply_gap_median_min·message_count
# 3개로 한정 + comment(방향 문장, 숫자 없음) 추가 — models/api.py RangeMetrics/BaselineMetrics/
# ReviewMetrics, services/projection.py 참고. message_length_median·session_length_median 은
# 이 화면에서 제외(리포트/타임라인에는 계속 있음). ⚠️ 프론트(Review.tsx 등, 시여 담당) 쪽도
# web/src/api/mock/review.json 새 형태에 맞춰 렌더링 수정 필요.
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError

from ..deps import current_member
from ..models.api import NoteCreateRequest, NoteResponse, ReviewResponse, Who
from ..services.projection import build_review

router = APIRouter(prefix="/api/couples", tags=["review"])

KST = timezone(timedelta(hours=9))

# 구간 저장형 (사람별 a/b). question_rate·reply_gap_median_min 은 {couple, a, b},
# message_count 는 구간 합산 스칼라(개인별 미제공, 2026-08-25 결정).
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
            "reply_gap_median_min": {"couple": 12, "a": 3, "b": 41},
            "message_count": 187,
        },
        "baseline": {
            "weeks": 8,
            "question_rate": {"couple": 0.23, "a": 0.22, "b": 0.24},
            "reply_gap_median_min": {"couple": 5, "a": 4, "b": 6},
            "message_count": 210,
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


def _with_timezone(value: datetime) -> datetime:
    """쿼리·본문에 timezone이 빠진 경우에도 API의 KST 기준으로 비교한다."""
    return value if value.tzinfo is not None else value.replace(tzinfo=KST)


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "VALIDATION_ERROR", "message": message},
    )


def _overlaps(start: datetime, end: datetime, item_start: datetime, item_end: datetime) -> bool:
    return item_start <= end and item_end >= start


def _notes_in_range(start: datetime, end: datetime) -> list[dict]:
    notes = []
    for note in _STORED["notes"]:
        note_start = _with_timezone(note.get("range_start") or note["created_at"])
        note_end = _with_timezone(note.get("range_end") or note["created_at"])
        if _overlaps(start, end, note_start, note_end):
            notes.append(note)
    return notes


@router.get("/{couple_id}/review", response_model=ReviewResponse)
async def review(
    couple_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    session_id: int | None = None,
    me: Who = Depends(current_member),
) -> ReviewResponse:
    if session_id is not None:
        selected = next((s for s in _STORED["sessions"] if s["session_id"] == session_id), None)
        if selected is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "세션을 찾을 수 없습니다"},
            )
        s = selected["started_at"]
        e = selected["ended_at"]
        sessions = [selected]
    else:
        if (start is None) != (end is None):
            raise _validation_error("start와 end를 함께 입력해주세요")
        s = _with_timezone(start or datetime(2026, 8, 17, 0, 0, tzinfo=KST))
        e = _with_timezone(end or datetime(2026, 8, 21, 0, 0, tzinfo=KST))
        if e < s:
            raise _validation_error("end는 start보다 빠를 수 없습니다")
        if e - s > timedelta(days=14):
            raise _validation_error("돌아보기 범위는 최대 14일입니다")
        sessions = [
            session
            for session in _STORED["sessions"]
            if _overlaps(s, e, session["started_at"], session["ended_at"])
        ]

    stored = {**_STORED, "sessions": sessions, "notes": _notes_in_range(s, e)}
    return build_review(stored, me, s, e)


@router.post("/{couple_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    couple_id: str,
    payload: dict[str, Any],
    me: Who = Depends(current_member),
) -> NoteResponse:
    try:
        body = NoteCreateRequest.model_validate(payload)
    except ValidationError as exc:
        raise _validation_error("메모 형식이 올바르지 않습니다") from exc

    range_start = _with_timezone(body.range_start)
    range_end = _with_timezone(body.range_end)
    if range_end < range_start:
        raise _validation_error("range_end는 range_start보다 빠를 수 없습니다")

    note = {
        "note_id": max((note["note_id"] for note in _STORED["notes"]), default=0) + 1,
        "author": me,
        "body": body.body,
        "range_start": range_start,
        "range_end": range_end,
        "created_at": datetime.now(KST),
    }
    _STORED["notes"].append(note)
    return NoteResponse.model_validate(note)


@router.delete("/{couple_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    couple_id: str,
    note_id: int,
    me: Who = Depends(current_member),
) -> Response:
    note_index = next(
        (index for index, note in enumerate(_STORED["notes"]) if note["note_id"] == note_id),
        None,
    )
    if note_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "메모를 찾을 수 없습니다"},
        )
    if _STORED["notes"][note_index]["author"] != me:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "메모 작성자만 삭제할 수 있습니다"},
        )
    _STORED["notes"].pop(note_index)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
