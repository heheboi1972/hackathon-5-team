"""라우터 공용 인증·커플 멤버 의존성."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models.api import Who
from .services.auth import InvalidToken, decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    email: str
    display_name: str
    couple_id: UUID | None = None
    member: Who | None = None
    couple_status: str | None = None


def _unauthorized(message: str = "인증이 필요합니다") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        user_id = decode_token(
            credentials.credentials, request.app.state.container.settings.jwt_secret
        )
    except InvalidToken as exc:
        raise _unauthorized(str(exc)) from exc

    row = await request.app.state.container.postgres.get_user_context(user_id)
    if row is None:
        raise _unauthorized("사용자를 찾을 수 없습니다")
    return AuthenticatedUser(**row)


async def current_member(
    couple_id: UUID,
    user: AuthenticatedUser = Depends(current_user),
) -> Who:
    """경로의 커플에서 현재 사용자의 a/b 역할을 반환한다."""
    if user.member is None or user.couple_id != couple_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_COUPLE_MEMBER",
                "message": "해당 커플의 구성원이 아닙니다",
            },
        )
    return user.member
