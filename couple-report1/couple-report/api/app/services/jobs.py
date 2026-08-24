"""비동기 잡 큐 자리표시자."""

from uuid import uuid4


def create_mock_job(kind: str = "report_backfill") -> dict[str, object]:
    return {
        "job_id": str(uuid4()),
        "kind": kind,
        "status": "done",
        "progress": {"total": 1, "done": 1, "failed": 0},
        "current_week": "2026-08-17",
    }

