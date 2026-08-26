"""FR-001 커플 초대·참여·확인·조회·해제."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from psycopg.errors import UniqueViolation

from ..deps import AuthenticatedUser, current_user
from ..models.api import (
    ActiveJob,
    ConfirmRequest,
    ConfirmResponse,
    CoupleData,
    CoupleMembers,
    CoupleMeResponse,
    CoupleSettingsUpdate,
    InviteResponse,
    JoinRequest,
    JoinResponse,
    MemberInfo,
    PartnerInfo,
)
from ..services.postgres_service import RepositoryError

router = APIRouter(prefix="/api/couples", tags=["couples"])
KST = ZoneInfo("Asia/Seoul")
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _repo_error(exc: RepositoryError) -> HTTPException:
    code_to_status = {
        "INVITE_INVALID": status.HTTP_404_NOT_FOUND,
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "FORBIDDEN": status.HTTP_403_FORBIDDEN,
    }
    return HTTPException(
        status_code=code_to_status.get(exc.code, status.HTTP_409_CONFLICT),
        detail={"code": exc.code, "message": exc.message},
    )


@router.post(
    "/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED
)
async def invite(
    request: Request, user: AuthenticatedUser = Depends(current_user)
) -> InviteResponse:
    row = None
    for _ in range(5):
        code = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))
        try:
            row = await request.app.state.container.postgres.create_or_get_invite(
                user.user_id, code, datetime.now(KST) + timedelta(days=7)
            )
            break
        except UniqueViolation:
            continue
        except RepositoryError as exc:
            raise _repo_error(exc) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "INVITE_CODE_UNAVAILABLE",
                "message": "초대 코드 발급을 다시 시도해주세요",
            },
        )
    return InviteResponse(
        couple_id=str(row["couple_id"]),
        invite_code=row["invite_code"],
        expires_at=row["expires_at"],
        status=row["status"],
    )


@router.post("/join", response_model=JoinResponse)
async def join(
    body: JoinRequest, request: Request, user: AuthenticatedUser = Depends(current_user)
) -> JoinResponse:
    try:
        row = await request.app.state.container.postgres.join_invite(
            user.user_id, body.invite_code.strip().upper()
        )
    except RepositoryError as exc:
        raise _repo_error(exc) from exc
    return JoinResponse(
        couple_id=str(row["couple_id"]),
        status=row["status"],
        partner=PartnerInfo(display_name=row["partner_name"]),
    )


@router.post("/{couple_id}/confirm", response_model=ConfirmResponse)
async def confirm(
    couple_id: UUID,
    body: ConfirmRequest,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
) -> ConfirmResponse:
    try:
        row = await request.app.state.container.postgres.confirm_couple(
            couple_id, user.user_id, body.accept
        )
    except RepositoryError as exc:
        raise _repo_error(exc) from exc
    return ConfirmResponse(couple_id=str(row["couple_id"]), status=row["status"])


@router.get("/me", response_model=CoupleMeResponse)
async def me(
    request: Request, user: AuthenticatedUser = Depends(current_user)
) -> CoupleMeResponse:
    row = await request.app.state.container.postgres.get_couple_me(user.user_id)
    if row is None:
        return CoupleMeResponse()

    members = None
    if row["user_b"] is not None:
        members = CoupleMembers(
            a=MemberInfo(
                user_id=str(row["user_a"]), display_name=row["display_name_a"]
            ),
            b=MemberInfo(
                user_id=str(row["user_b"]), display_name=row["display_name_b"]
            ),
        )
    kakao_names = None
    if row["kakao_name_a"] and row["kakao_name_b"]:
        kakao_names = {"a": row["kakao_name_a"], "b": row["kakao_name_b"]}
    data = None
    if row["first_week"] is not None and row["last_week"] is not None:
        data = CoupleData(
            first_week=row["first_week"],
            last_week=row["last_week"],
            weeks_available=row["weeks_available"],
            message_count=row["message_count"],
        )
    active_job = None
    if row["active_job_id"] is not None:
        active_job = ActiveJob(
            job_id=str(row["active_job_id"]),
            kind=row["active_job_kind"],
            done=row["active_job_done"],
            total=row["active_job_total"],
        )
    return CoupleMeResponse(
        couple_id=str(row["couple_id"]),
        status=row["status"],
        members=members,
        me=row["me"],
        kakao_names=kakao_names,
        started_at=row["started_at"],
        first_met_at=row["first_met_at"],
        data=data,
        active_job=active_job,
    )


@router.patch("/me", response_model=CoupleMeResponse)
async def update_me(
    body: CoupleSettingsUpdate,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
) -> CoupleMeResponse:
    if user.couple_id is None or user.member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_COUPLE_MEMBER",
                "message": "현재 연결된 커플이 없습니다",
            },
        )

    updated = await request.app.state.container.postgres.update_couple_first_met_at(
        user.couple_id, user.user_id, body.first_met_at
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_COUPLE_MEMBER",
                "message": "해당 커플의 구성원이 아닙니다",
            },
        )
    return await me(request, user)


@router.delete("/{couple_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dissolve(
    couple_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
) -> Response:
    couple = await request.app.state.container.postgres.get_active_couple(
        couple_id, user.user_id
    )
    if couple is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "커플을 찾을 수 없습니다"},
        )
    if couple["member"] is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "이 커플의 멤버가 아닙니다"},
        )
    try:
        # 외부 저장소를 먼저 지우면 DB 삭제 실패 시에도 재시도로 안전하게 수렴한다.
        await request.app.state.container.qdrant.delete_by_couple(str(couple_id))
        await request.app.state.container.postgres.dissolve_couple(
            couple_id, user.user_id
        )
    except RepositoryError as exc:
        raise _repo_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
