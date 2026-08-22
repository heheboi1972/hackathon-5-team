# 역할: Postgres 연결 풀 + repo 함수 (couples, messages, metrics, reports, notes) (참조: TRD §2.1, §4.1)
# 스캐폴딩: 풀 관리·ping만. repo 함수는 TODO(윤석) — ORM 없이 직접 SQL
from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


class PostgresService:
    def __init__(self, dsn: str):
        self.pool = AsyncConnectionPool(dsn, min_size=1, max_size=5, open=False)

    async def open(self, timeout: float = 10.0) -> None:
        await self.pool.open()
        await self.pool.wait(timeout=timeout)

    async def close(self) -> None:
        await self.pool.close()

    async def ping(self) -> bool:
        try:
            async with self.pool.connection(timeout=3) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning("postgres ping 실패: %s", e)
            return False

    # ------------------------------------------------------------ repo (TODO 윤석)
    # async def get_couple(self, couple_id) -> Couple | None: ...
    # async def insert_messages(self, couple_id, rows) -> int: ...
    # async def upsert_weekly_metrics(self, couple_id, week_start, summary, outliers): ...
    # async def upsert_report(self, couple_id, week_start, status, report, trace): ...
