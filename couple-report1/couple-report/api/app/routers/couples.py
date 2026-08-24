"""FR-001 커플 연결 API Mock 라우터."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Response, status

from app.deps import CurrentMember
from app.models.api import (
    ConfirmRequest,
    CoupleMeResponse,
    CoupleStatusResponse,
    InviteResponse,
    JoinRequest,
    JoinResponse,
    Member,
    Partner,
)


router = APIRouter(prefix="/api/couples", tags=["couples"])
COUPLE_ID = "00000000-0000-4000-8000-000000000001"


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite(_: CurrentMember) -> InviteResponse:
    return InviteResponse(
        couple_id=COUPLE_ID,
        invite_code="K7P2M9QX",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        status="pending",
    )


@router.post("/join", response_model=JoinResponse)
async def join(_: JoinRequest, member: CurrentMember) -> JoinResponse:
    del member
    return JoinResponse(
        couple_id=COUPLE_ID,
        status="awaiting_confirm",
        partner=Partner(display_name="Mock 파트너"),
    )


@router.post("/{couple_id}/confirm", response_model=CoupleStatusResponse)
async def confirm(couple_id: str, payload: ConfirmRequest, _: CurrentMember) -> CoupleStatusResponse:
    return CoupleStatusResponse(couple_id=couple_id, status="active" if payload.accept else "pending")


@router.get("/me", response_model=CoupleMeResponse)
async def me(member: CurrentMember) -> CoupleMeResponse:
    return CoupleMeResponse(
        couple_id=COUPLE_ID,
        status="active",
        members={
            "a": Member(user_id="00000000-0000-4000-8000-00000000000a", display_name="Mock A"),
            "b": Member(user_id="00000000-0000-4000-8000-00000000000b", display_name="Mock B"),
        },
        me=member,
        kakao_names={"a": "카카오 A", "b": "카카오 B"},
        started_at=date(2026, 3, 1),
        data={
            "first_week": "2026-03-02",
            "last_week": "2026-08-17",
            "weeks_available": 25,
            "message_count": 18342,
        },
        active_job=None,
    )


@router.delete("/{couple_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_couple(couple_id: str, _: CurrentMember) -> Response:
    del couple_id
    return Response(status_code=status.HTTP_204_NO_CONTENT)

