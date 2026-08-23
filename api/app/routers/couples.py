# 역할: FR-001 커플 연결 — invite/join/confirm/me/DELETE (참조: API_SPEC §2)
# 스캐폴딩 스텁: 고정 응답만. 상태 전이 검증·DB는 TODO(윤석)
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Response, status

from ..models.api import (
    ConfirmRequest,
    ConfirmResponse,
    CoupleData,
    CoupleMembers,
    CoupleMeResponse,
    InviteResponse,
    JoinRequest,
    JoinResponse,
    MemberInfo,
    PartnerInfo,
)

router = APIRouter(prefix="/api/couples", tags=["couples"])

KST = timezone(timedelta(hours=9))
MOCK_COUPLE_ID = "00000000-0000-0000-0000-000000000001"


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite() -> InviteResponse:
    return InviteResponse(
        couple_id=MOCK_COUPLE_ID,
        invite_code="K7P2M9QX",
        expires_at=datetime.now(KST) + timedelta(days=7),
        status="pending",
    )


@router.post("/join", response_model=JoinResponse)
async def join(body: JoinRequest) -> JoinResponse:
    return JoinResponse(
        couple_id=MOCK_COUPLE_ID,
        status="awaiting_confirm",
        partner=PartnerInfo(display_name="형준"),
    )


@router.post("/{couple_id}/confirm", response_model=ConfirmResponse)
async def confirm(couple_id: str, body: ConfirmRequest) -> ConfirmResponse:
    return ConfirmResponse(couple_id=couple_id, status="active" if body.accept else "pending")


@router.get("/me", response_model=CoupleMeResponse)
async def me() -> CoupleMeResponse:
    return CoupleMeResponse(
        couple_id=MOCK_COUPLE_ID,
        status="active",
        members=CoupleMembers(
            a=MemberInfo(user_id="00000000-0000-0000-0000-00000000000a", display_name="형준"),
            b=MemberInfo(user_id="00000000-0000-0000-0000-00000000000b", display_name="윤아"),
        ),
        me="a",
        kakao_names={"a": "김형준", "b": "윤아♥"},
        started_at=date(2026, 3, 1),
        active_job=None,   # TODO(윤석): jobs 에서 status IN (queued, running) 최신 1건 (API_SPEC §2.4)
        data=CoupleData(
            first_week=date(2026, 3, 2),
            last_week=date(2026, 8, 17),
            weeks_available=25,
            message_count=18342,
        ),
    )


@router.delete("/{couple_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dissolve(couple_id: str) -> Response:
    # TODO(윤석): Postgres CASCADE + Qdrant couple_id 필터 삭제 (API_SPEC §2.5)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
