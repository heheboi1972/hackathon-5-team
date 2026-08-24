"""API_SPEC.md의 외부 엔드포인트 라우터 모음."""

from app.routers import auth, chat, couples, health, reports, review, timeline, upload

__all__ = ["auth", "chat", "couples", "health", "reports", "review", "timeline", "upload"]

