# 역할: FR-002 업로드 — POST /api/couples/{id}/upload, GET /api/jobs/{id} (참조: API_SPEC §3)
# 스캐폴딩 스텁: 파일을 받기만 하고 고정 202 응답. 파싱→지표→작업 큐는 TODO(윤석)
import uuid
from datetime import date

from fastapi import APIRouter, File, Form, UploadFile, status

from ..models.api import (
    DateRange,
    JobProgress,
    JobRef,
    JobResponse,
    ParsedInfo,
    ReportJobsInfo,
    UploadResponse,
)

router = APIRouter(prefix="/api", tags=["upload"])


@router.post(
    "/couples/{couple_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    couple_id: str,
    file: UploadFile = File(...),
    name_map: str | None = Form(default=None),
) -> UploadResponse:
    await file.read()  # 스텁: 수신만 확인
    return UploadResponse(
        job_id=str(uuid.uuid4()),
        parsed=ParsedInfo(
            format="ios",
            message_count=18342,
            new_messages=412,
            session_count=1203,
            range=DateRange.model_validate({"from": "2026-03-02", "to": "2026-08-21"}),
        ),
        weeks_computed=25,
        report_jobs=ReportJobsInfo(total=25, pending=25),
        embed_job=JobRef(job_id=str(uuid.uuid4())),   # embed_sessions 잡 — 리포트 잡보다 먼저 (API_SPEC §3.1 규칙 9)
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    # 스텁: 항상 완료 상태 — 프론트 폴링 종료 조건 확인용
    return JobResponse(
        job_id=job_id,
        kind="report_backfill",
        status="done",
        progress=JobProgress(total=25, done=25, failed=0),
        current_week=date(2026, 8, 17),
    )
