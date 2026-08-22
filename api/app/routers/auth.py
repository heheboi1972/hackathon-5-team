# 역할: FR-000 인증 — POST /api/auth/signup, /api/auth/login (참조: API_SPEC §1)
# 스캐폴딩 스텁: 고정/결정적 응답만. 실제 JWT·DB 저장은 TODO(윤석) — services/auth.py 경유로 교체
import uuid

from fastapi import APIRouter, status

from ..models.api import AuthResponse, LoginRequest, SignupRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])

_NS = uuid.UUID("00000000-0000-0000-0000-00000000feed")  # 이메일→user_id 결정적 생성용


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest) -> AuthResponse:
    user_id = str(uuid.uuid5(_NS, body.email))
    return AuthResponse(user_id=user_id, token=f"mock-token-{user_id}")


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    user_id = str(uuid.uuid5(_NS, body.email))
    return AuthResponse(user_id=user_id, token=f"mock-token-{user_id}")
