"""FR-002 업로드 및 잡 조회 API Mock 라우터."""

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile, status

from app.deps import CurrentMember
from app.models.api import JobResponse, UploadResponse


router = APIRouter(tags=["upload"])


@router.post(
    "/api/couples/{couple_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_conversation(
    couple_id: str,
    _: CurrentMember,
    file: UploadFile = File(...),
    name_map: str | None = Form(default=None),
) -> UploadResponse:
    del couple_id, name_map
    report_job_id = str(uuid4())
    embed_job_id = str(uuid4())
    detected_format = "ios" if (file.filename or "").lower().endswith(".zip") else "pc"
    return UploadResponse(
        job_id=report_job_id,
        embed_job={"job_id": embed_job_id},
        parsed={
            "format": detected_format,
            "message_count": 42,
            "new_messages": 42,
            "session_count": 3,
            "range": {"from": "2026-08-17", "to": "2026-08-23"},
        },
        weeks_computed=1,
        report_jobs={"total": 1, "pending": 0},
    )


@router.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, _: CurrentMember) -> JobResponse:
    return JobResponse(
        job_id=job_id,
        kind="report_backfill",
        status="done",
        progress={"total": 1, "done": 1, "failed": 0},
        current_week=date(2026, 8, 17),
    )

