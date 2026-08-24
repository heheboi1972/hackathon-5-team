"""비밀번호 해시와 JWT 발급/검증."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from passlib.context import CryptContext

_PASSWORDS = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")
_ALGORITHM = "HS256"


class InvalidToken(ValueError):
    """서명, 만료 시각 또는 subject가 올바르지 않은 토큰."""


def hash_password(password: str) -> str:
    return _PASSWORDS.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _PASSWORDS.verify(password, password_hash)


def issue_token(user_id: str | UUID, secret: str, expire_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=expire_minutes),
        },
        secret,
        algorithm=_ALGORITHM,
    )


def decode_token(token: str, secret: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidToken("유효하지 않거나 만료된 토큰입니다") from exc
