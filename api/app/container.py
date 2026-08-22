# 역할: services + agents + supervisors 의존성 묶음 (참조: SCAFFOLD §2)
# lifespan(main.py)에서 build_container() 로 생성 → app.state.container
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import Settings
from .services.ai_service import AIService, build_ai_service
from .services.postgres_service import PostgresService
from .services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    ai: AIService
    postgres: PostgresService
    qdrant: QdrantService
    postgres_up: bool = False
    qdrant_up: bool = False
    # TODO(윤석): agents = {select, interpret, suggest, safety}, report_supervisor, chat_supervisor

    async def postgres_ok(self) -> bool:
        return self.postgres_up and await self.postgres.ping()

    async def qdrant_ok(self) -> bool:
        return self.qdrant_up and await self.qdrant.ping()

    async def close(self) -> None:
        await self.postgres.close()
        await self.qdrant.close()
        await self.ai.close()


async def build_container(settings: Settings) -> Container:
    ai = build_ai_service(settings)
    pg = PostgresService(settings.postgres_dsn)
    qd = QdrantService(settings.qdrant_url, settings.qdrant_collection_conv, settings.qdrant_collection_knowledge)
    c = Container(settings=settings, ai=ai, postgres=pg, qdrant=qd)

    # 저장소가 아직 안 떴어도 앱은 뜬다 — /health/ready 가 503으로 알려줌
    try:
        await pg.open()
        c.postgres_up = True
    except Exception as e:
        logger.warning("postgres 연결 실패 (ready=false로 기동): %s", e)
    try:
        await qd.ensure_collections(vector_size=ai.vector_size)
        c.qdrant_up = True
    except Exception as e:
        logger.warning("qdrant 연결 실패 (ready=false로 기동): %s", e)

    return c
