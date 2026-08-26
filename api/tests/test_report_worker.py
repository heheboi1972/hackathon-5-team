"""TASKS 3-5 최신 주차 우선·동시성·격리·hash skip 계약."""

import asyncio
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.services.jobs import ReportJobHandler, ReportJobPartialFailure


class _Repo:
    def __init__(self, rows):
        self.rows = rows
        self.saved = []
        self.failures = []
        self.progress = []
        self.total = None

    async def get_report_job_weeks(self, _job): return self.rows
    async def set_job_total(self, _job_id, total): self.total = total
    async def update_job_progress(self, _job_id, **kwargs): self.progress.append(kwargs)
    async def save_report(self, couple_id, week, status, report, summary_hash):
        assert report["execution_trace"][-1]["step"] == "persist"
        assert report["execution_trace"][-1]["status"] == "ok"
        self.saved.append((week, status, report, summary_hash))
    async def save_report_failure(self, couple_id, week, trace_id, trace, error, summary_hash):
        self.failures.append((week, trace_id, trace, error))


class _Supervisor:
    def __init__(self, failed_week=None):
        self.failed_week = failed_week
        self.active = self.peak = 0
        self.started = []

    async def run(self, row):
        self.started.append(row["week_start"])
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        if row["week_start"] == self.failed_week:
            raise RuntimeError("boom")
        return {"status": "generated", "report": {"status": "generated"},
                "trace_id": str(uuid4()),
                "execution_trace": [{"step": "persist", "status": "pending"}]}


def _rows(count=5):
    couple = uuid4()
    newest = date(2026, 8, 24)
    return [{"couple_id": couple, "week_start": newest - timedelta(weeks=i),
             "summary_hash": str(i) * 64, "report_summary_hash": None,
             "report_status": "pending"} for i in range(count)]


def test_backfill_is_newest_first_bounded_to_three_and_isolates_failure():
    async def scenario():
        rows = _rows()
        repo, supervisor = _Repo(rows), _Supervisor(rows[1]["week_start"])
        handler = ReportJobHandler(repo, supervisor, 3)
        with pytest.raises(ReportJobPartialFailure):
            await handler({"job_id": uuid4(), "kind": "report_backfill"})
        assert supervisor.started == [row["week_start"] for row in rows]
        assert supervisor.peak == 3
        assert len(repo.saved) == 4 and len(repo.failures) == 1
        assert repo.progress[-1]["done"] == 4 and repo.progress[-1]["failed"] == 1
        assert repo.progress[-1]["current_week"] is None
    asyncio.run(scenario())


def test_unchanged_hash_skips_backfill_but_report_single_forces_generation():
    async def scenario():
        row = _rows(1)[0]
        row.update(report_summary_hash=row["summary_hash"], report_status="generated")
        repo, supervisor = _Repo([row]), _Supervisor()
        await ReportJobHandler(repo, supervisor)({"job_id": uuid4(), "kind": "report_backfill"})
        assert supervisor.started == [] and repo.saved == []
        await ReportJobHandler(repo, supervisor)({"job_id": uuid4(), "kind": "report_single"})
        assert supervisor.started == [row["week_start"]] and len(repo.saved) == 1
    asyncio.run(scenario())
