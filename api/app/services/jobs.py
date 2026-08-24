"""Postgres jobs 테이블을 소비하는 비동기 워커 루프."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .postgres_service import PostgresService

logger = logging.getLogger(__name__)
JobHandler = Callable[[dict[str, Any]], Awaitable[None]]


class JobService:
    def __init__(self, postgres: PostgresService, poll_interval: float = 0.5):
        self.postgres = postgres
        self.poll_interval = poll_interval
        self.handlers: dict[str, JobHandler] = {}
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()

    def register(self, kind: str, handler: JobHandler) -> None:
        self.handlers[kind] = handler
        self._wake.set()

    async def start(self) -> None:
        if self._task is not None:
            return
        recovered = await self.postgres.recover_running_jobs()
        if recovered:
            logger.warning(
                "재시작 중 running 잡 %d개를 queued로 복구했습니다", recovered
            )
        self._task = asyncio.create_task(self._run(), name="postgres-job-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _wait(self) -> None:
        self._wake.clear()
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=self.poll_interval)
        except TimeoutError:
            pass

    async def _run(self) -> None:
        while True:
            try:
                job = await self.postgres.claim_next_job(tuple(self.handlers))
                if job is None:
                    await self._wait()
                    continue
                handler = self.handlers[job["kind"]]
                try:
                    await handler(job)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception(
                        "잡 실패: job_id=%s kind=%s", job["job_id"], job["kind"]
                    )
                    await self.postgres.finish_job(job["job_id"], error=str(exc)[:4000])
                else:
                    await self.postgres.finish_job(job["job_id"])
            except asyncio.CancelledError:
                raise
            except Exception:
                # DB 일시 장애가 워커 자체를 죽이지 않게 한다.
                logger.exception("잡 워커 루프 오류")
                await self._wait()
