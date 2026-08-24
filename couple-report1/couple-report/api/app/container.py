"""서비스와 에이전트 의존성을 한곳에 보관하는 최소 컨테이너."""

from dataclasses import dataclass

from app.config import Settings
from app.services.ai_service import AIService, build_ai_service


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    ai_service: AIService


def build_container(settings: Settings) -> AppContainer:
    return AppContainer(settings=settings, ai_service=build_ai_service(settings))

