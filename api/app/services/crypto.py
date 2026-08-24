"""카카오톡 본문 암호화/복호화 (Fernet)."""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class BodyCipher:
    def __init__(
        self,
        encryption_key: str,
        *,
        fallback_secret: str = "",
        production: bool = False,
    ):
        key = encryption_key.strip().encode()
        if not key:
            if production:
                raise ValueError("production에서는 ENCRYPTION_KEY가 필수입니다")
            logger.warning("ENCRYPTION_KEY가 없어 로컬 개발용 파생 키를 사용합니다")
            key = base64.urlsafe_b64encode(
                hashlib.sha256(fallback_secret.encode()).digest()
            )
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("ENCRYPTION_KEY는 Fernet 키 형식이어야 합니다") from exc

    def encrypt(self, body: str) -> bytes:
        return self._fernet.encrypt(body.encode("utf-8"))

    def decrypt(self, encrypted: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(encrypted)).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("저장된 메시지를 복호화할 수 없습니다") from exc
