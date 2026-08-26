# 역할: services + agents + supervisors 의존성 묶음 (참조: SCAFFOLD §2)
# lifespan(main.py)에서 build_container() 로 생성 → app.state.container
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from .agents.interpret_agent import InterpretAgent
from .agents.report_supervisor import ReportSupervisor
from .agents.safety_agent import SafetyAgent
from .agents.select_agent import SelectAgent
from .agents.suggest_agent import SuggestAgent
from .config import Settings
from .services.ai_service import AIService, build_ai_service
from .services.crypto import BodyCipher
from .services.embed_sessions import run_embed_sessions_job
from .services.jobs import JobService, ReportJobHandler
from .services.knowledge import Knowledge, load_knowledge
from .services.lexicon import BuildLexiconService
from .services.postgres_service import PostgresService
from .services.qdrant_service import QdrantService
from .services.term_search import TermSearchService
from .tools.get_suggestion_templates import get_suggestion_templates
from .tools.search_conversation import search_conversation
from .tools.search_knowledge import search_knowledge

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    ai: AIService
    postgres: PostgresService
    qdrant: QdrantService
    cipher: BodyCipher
    jobs: JobService
    knowledge: Knowledge
    lexicon: BuildLexiconService
    report_supervisor: ReportSupervisor
    report_jobs: ReportJobHandler
    term_search: TermSearchService
    postgres_up: bool = False
    qdrant_up: bool = False

    async def postgres_ok(self) -> bool:
        return self.postgres_up and await self.postgres.ping()

    async def qdrant_ok(self) -> bool:
        return self.qdrant_up and await self.qdrant.ping()

    async def close(self) -> None:
        await self.jobs.stop()
        await self.postgres.close()
        await self.qdrant.close()
        await self.ai.close()


async def build_container(settings: Settings) -> Container:
    ai = build_ai_service(settings)
    pg = PostgresService(settings.postgres_dsn)
    qd = QdrantService(
        settings.qdrant_url,
        settings.qdrant_collection_conv,
    )

    cipher = BodyCipher(
        settings.encryption_key,
        fallback_secret=settings.jwt_secret,
        production=settings.app_env.lower() in {"prod", "production"},
    )

    jobs = JobService(pg)

    knowledge = load_knowledge(Path(settings.knowledge_dir))

    lexicon = BuildLexiconService(
        pg,
        ai,
        cipher,
        knowledge.seed_lexicon,
    )

    jobs.register(
        "build_lexicon",
        lexicon.handle_job,
    )

    def suggestion_tool(metric: str, direction: str):
        return get_suggestion_templates(
            knowledge,
            metric,
            direction,
        )

    if ai.provider_name == "mock":

        async def conversation_tool(*_args, **_kwargs):
            return []

    else:
        conversation_context = SimpleNamespace(
            ai=ai,
            qdrant=qd,
            postgres=pg,
            cipher=cipher,
        )

        conversation_tool = partial(
            search_conversation,
            conversation_context,
        )

    select = SelectAgent(ai)

    interpret = InterpretAgent(
        ai,
        conversation_tool,
        partial(search_knowledge, knowledge),
    )

    suggest = SuggestAgent(
        ai,
        suggestion_tool,
    )

    safety = SafetyAgent(ai)

    supervisor = ReportSupervisor(
        select,
        interpret,
        suggest,
        safety,
    )

    report_jobs = ReportJobHandler(
        pg,
        supervisor,
        max_concurrency=3,
    )

    term_search = TermSearchService(
        pg,
        cipher,
    )

    jobs.register(
        "report_backfill",
        report_jobs,
    )

    jobs.register(
        "report_single",
        report_jobs,
    )

    c = Container(
        settings=settings,
        ai=ai,
        postgres=pg,
        qdrant=qd,
        cipher=cipher,
        jobs=jobs,
        knowledge=knowledge,
        lexicon=lexicon,
        report_supervisor=supervisor,
        report_jobs=report_jobs,
        term_search=term_search,
    )

    jobs.register(
        "embed_sessions",
        lambda job: run_embed_sessions_job(c, job),
    )

    # 저장소가 아직 안 떠 있어도 앱 자체는 기동한다.
    # /health/ready에서 연결 상태를 확인한다.
    try:
        await pg.open()
        c.postgres_up = True
        await jobs.start()
    except Exception as e:
        c.postgres_up = False
        logger.warning(
            "postgres 연결 실패 (ready=false로 기동): %s",
            e,
        )

    try:
        await qd.ensure_collections(
            vector_size=ai.vector_size,
        )
        c.qdrant_up = True
    except Exception as e:
        c.qdrant_up = False
        logger.warning(
            "qdrant 연결 실패 (ready=false로 기동): %s",
            e,
        )

    return c