"""Mock 우선 AI provider 인터페이스. 실제 watsonx 연동은 후속 구현 대상."""

from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings


class AIService(Protocol):
    provider: str

    async def generate(self, prompt: str, **kwargs: Any) -> str: ...


@dataclass(slots=True)
class MockAIService:
    provider: str = "mock"

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Mock AI 응답입니다."


def build_ai_service(settings: Settings) -> AIService:
    if settings.ai_provider != "mock":
        raise RuntimeError("현재 스캐폴드는 AI_PROVIDER=mock만 지원합니다.")
    return MockAIService()

