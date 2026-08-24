"""FR-000 인증 API Mock 라우터."""

from uuid import uuid4

from fastapi import APIRouter, status

from app.models.api import AuthResponse, LoginRequest, SignupRequest
from app.services.auth import issue_mock_token


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(_: SignupRequest) -> AuthResponse:
    user_id = str(uuid4())
    return AuthResponse(user_id=user_id, token=issue_mock_token(user_id))


@router.post("/login", response_model=AuthResponse)
async def login(_: LoginRequest) -> AuthResponse:
    user_id = "00000000-0000-4000-8000-00000000000a"
    return AuthResponse(user_id=user_id, token=issue_mock_token(user_id))

