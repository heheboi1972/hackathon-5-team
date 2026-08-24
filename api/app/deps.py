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


async def current_member(user: AuthenticatedUser = Depends(current_user)) -> Who:
    """현재 커플에서의 a/b 역할. projection의 `mine`을 결정하는 유일한 경로."""
    if user.member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "COUPLE_REQUIRED", "message": "먼저 커플을 연결해주세요"},
        )
    return user.member
