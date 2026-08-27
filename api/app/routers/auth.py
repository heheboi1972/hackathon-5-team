"""FR-000 회원가입·로그인."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, status

from ..models.api import AuthResponse, LoginRequest, SignupRequest
from ..services.auth import hash_password, issue_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token(request: Request, user_id: str) -> str:
    settings = request.app.state.container.settings
    return issue_token(user_id, settings.jwt_secret, settings.jwt_expire_minutes)


@router.post(
    "/signup",
    response_model=AuthResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def signup(body: SignupRequest, request: Request) -> AuthResponse:
    email = str(body.email).strip().casefold()
    password_hash = await asyncio.to_thread(hash_password, body.password)
    user_id = await request.app.state.container.postgres.create_user(
        email, password_hash, body.display_name.strip()
    )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "이미 가입된 이메일입니다"},
        )
    return AuthResponse(user_id=str(user_id), token=_token(request, str(user_id)))


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request) -> AuthResponse:
    row = await request.app.state.container.postgres.get_user_by_email(
        str(body.email).strip().casefold()
    )
    valid = row is not None and await asyncio.to_thread(
        verify_password, body.password, row["password_hash"]
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "이메일 또는 비밀번호가 올바르지 않습니다",
            },
        )
    return AuthResponse(
        user_id=str(row["user_id"]),
        token=_token(request, str(row["user_id"])),
        couple_id=str(row["couple_id"]) if row.get("couple_id") else None,
        couple_status=row.get("couple_status"),
    )
