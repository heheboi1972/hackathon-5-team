# 역할: FR-005 돌아보기 — GET review, POST/DELETE notes (참조: API_SPEC §5) — 시여 담당 영역
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_review 만 호출 (ISSUE B3).
# 지표는 {couple, mine} — 상대 값 미전송. 타입은 models.api의 review 전용 모델로 고정한다.
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError

from ..deps import AuthenticatedUser, current_member, current_user
from ..models.api import (
    NoteCreateRequest,
    NoteResponse,
    ReviewResponse,
    ReviewSessionMessage,
    ReviewSessionMessagesResponse,
    Who,
)
from ..services.projection import build_review
from ..services.review_metrics import build_stored_review

router = APIRouter(prefix="/api/couples", tags=["review"])
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _with_timezone(value: datetime) -> datetime:
    """쿼리·본문에 timezone이 빠진 경우에도 API의 KST 기준으로 비교한다."""
    return value if value.tzinfo is not None else value.replace(tzinfo=KST)


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "VALIDATION_ERROR", "message": message},
    )


@router.get("/{couple_id}/review", response_model=ReviewResponse)
async def review(
    couple_id: UUID,
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    session_id: int | None = None,
    me: Who = Depends(current_member),
) -> ReviewResponse:
    if session_id is not None:
        mode = "session"
        query_start = query_end = None
    else:
        if (start is None) != (end is None):
            raise _validation_error("start와 end를 함께 입력해주세요")
        if start is None or end is None:
            raise _validation_error("start와 end를 입력하거나 session_id를 입력해주세요")
        query_start = _with_timezone(start)
        query_end = _with_timezone(end)
        if query_end < query_start:
            raise _validation_error("end는 start보다 빠를 수 없습니다")
        if query_end - query_start > timedelta(days=14):
            raise _validation_error("돌아보기 범위는 최대 14일입니다")
        mode = "date"

    raw = await request.app.state.container.postgres.get_review_data(
        couple_id,
        start=query_start,
        end=query_end,
        session_id=session_id,
    )
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "세션을 찾을 수 없습니다"},
        )
    stored = build_stored_review(raw, mode=mode)
    return build_review(stored, me, raw["range_start"], raw["range_end"])


@router.get(
    "/{couple_id}/review/sessions/{session_id}/messages",
    response_model=ReviewSessionMessagesResponse,
)
async def review_session_messages(
    couple_id: UUID,
    session_id: int,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    me: Who = Depends(current_member),
) -> ReviewSessionMessagesResponse:
    page = await request.app.state.container.postgres.get_review_session_messages(
        couple_id,
        session_id,
        offset=offset,
        limit=limit,
    )
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "대화 세션을 찾을 수 없습니다"},
        )

    try:
        messages = [
            ReviewSessionMessage(
                message_id=row["message_id"],
                at=row["sent_at"],
                mine=row["sender"] == me,
                text=request.app.state.container.cipher.decrypt(row["body_enc"]),
            )
            for row in page["messages"]
        ]
    except Exception as exc:
        logger.warning(
            "Could not decrypt review session messages couple_id=%s session_id=%s",
            couple_id,
            session_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "MESSAGE_DECRYPT_FAILED", "message": "대화 메시지를 불러오지 못했습니다"},
        ) from exc

    next_offset = offset + len(messages)
    return ReviewSessionMessagesResponse(
        session_id=session_id,
        total=page["total"],
        messages=messages,
        next_offset=next_offset if next_offset < page["total"] else None,
    )


@router.post("/{couple_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    couple_id: UUID,
    payload: dict[str, Any],
    request: Request,
    me: Who = Depends(current_member),
    user: AuthenticatedUser = Depends(current_user),
) -> NoteResponse:
    try:
        body = NoteCreateRequest.model_validate(payload)
    except ValidationError as exc:
        raise _validation_error("메모 형식이 올바르지 않습니다") from exc

    range_start = _with_timezone(body.range_start)
    range_end = _with_timezone(body.range_end)
    if range_end < range_start:
        raise _validation_error("range_end는 range_start보다 빠를 수 없습니다")

    row = await request.app.state.container.postgres.create_note(
        couple_id, user.user_id, range_start, range_end, body.body
    )
    return NoteResponse.model_validate({**row, "author": me})


@router.delete("/{couple_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    couple_id: UUID,
    note_id: int,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
    me: Who = Depends(current_member),
) -> Response:
    author = await request.app.state.container.postgres.get_note_author(couple_id, note_id)
    if author is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "메모를 찾을 수 없습니다"},
        )
    if author != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "메모 작성자만 삭제할 수 있습니다"},
        )
    await request.app.state.container.postgres.delete_note(couple_id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
