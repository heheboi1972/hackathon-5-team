"""Postgres jobs 테이블을 소비하는 비동기 워커 루프."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any
from uuid import uuid4

from ..agents.report_supervisor import ReportGenerationError, ReportSupervisor
from .postgres_service import PostgresService

logger = logging.getLogger(__name__)
JobHandler = Callable[[dict[str, Any]], Awaitable[None]]


class ReportJobPartialFailure(RuntimeError):
    pass


class ReportJobHandler:
    """report_backfill/report_single을 주차별로 격리해 최대 세 개 동시 실행한다."""

    def __init__(self, postgres: PostgresService, supervisor: ReportSupervisor,
                 max_concurrency: int = 3):
        self.postgres = postgres
        self.supervisor = supervisor
        self.max_concurrency = max_concurrency

    async def __call__(self, job: dict[str, Any]) -> None:
        force = job["kind"] == "report_single"
        rows = await self.postgres.get_report_job_weeks(job)
        await self.postgres.set_job_total(job["job_id"], len(rows))
        semaphore = asyncio.Semaphore(self.max_concurrency)
        lock = asyncio.Lock()
        done = failed = 0

        async def progress(week: date, ok: bool) -> None:
            nonlocal done, failed
            async with lock:
                if ok:
                    done += 1
                else:
                    failed += 1
                await self.postgres.update_job_progress(
                    job["job_id"], done=done, failed=failed, current_week=week)

        async def one(row: dict[str, Any]) -> None:
            async with semaphore:
                if (not force and row.get("report_summary_hash") == row.get("summary_hash")
                        and row.get("report_status") in {"generated", "insufficient_baseline"}):
                    await progress(row["week_start"], True)
                    return
                try:
                    generated = await self.supervisor.run(row)
                    trace = generated["execution_trace"]
                    trace.append({"step": "persist", "status": "ok", "input": {},
                                  "output": {"status": generated["status"]}, "error": None})
                    report_json = {**generated["report"], "trace_id": generated["trace_id"],
                                   "execution_trace": trace}
                    await self.postgres.save_report(
                        row["couple_id"], row["week_start"], generated["status"],
                        report_json, row.get("summary_hash"))
                except ReportGenerationError as exc:
                    trace = [*exc.execution_trace,
                             {"step": "persist", "status": "failed", "input": {},
                              "output": {}, "error": str(exc)[:1000]}]
                    await self.postgres.save_report_failure(
                        row["couple_id"], row["week_start"], exc.trace_id,
                        trace, str(exc), row.get("summary_hash"))
                    await progress(row["week_start"], False)
                    return
                except Exception as exc:
                    await self.postgres.save_report_failure(
                        row["couple_id"], row["week_start"], str(uuid4()),
                        [{"step": "worker", "status": "failed", "input": {},
                          "output": {}, "error": str(exc)[:1000]}], str(exc),
                        row.get("summary_hash"))
                    await progress(row["week_start"], False)
                    return
                await progress(row["week_start"], True)

        # repository가 최신 주차 우선으로 반환하며 task 생성 순서도 그대로 유지한다.
        await asyncio.gather(*(one(row) for row in rows))
        await self.postgres.update_job_progress(
            job["job_id"], done=done, failed=failed, current_week=None)
        if failed:
            raise ReportJobPartialFailure(f"{failed}개 주차 리포트 생성 실패")


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
