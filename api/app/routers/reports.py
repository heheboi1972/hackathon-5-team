# 역할: FR-004 리포트 — GET /api/couples/{id}/reports/{week}, POST regenerate (참조: API_SPEC §4.2~4.3)
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..deps import current_member
from ..models.api import RegenerateResponse, ReportResponse, Who
from ..services.projection import build_report

router = APIRouter(prefix="/api/couples", tags=["reports"])


@router.get("/{couple_id}/reports/{week_start}", response_model=ReportResponse)
async def get_report(
    request: Request,
    couple_id: UUID,
    week_start: date,
    me: Who = Depends(current_member),
) -> ReportResponse:
    if week_start.weekday() != 0:  # 월요일만 허용 (API_SPEC §4.2)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "week_start는 월요일이어야 합니다"},
        )
    stored = await request.app.state.container.postgres.get_report_record(couple_id, week_start)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "리포트 주차를 찾을 수 없습니다"},
        )
    return build_report(stored, me, week_start)


@router.post(
    "/{couple_id}/reports/{week_start}/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate(
    request: Request,
    couple_id: UUID,
    week_start: date,
    _me: Who = Depends(current_member),
) -> RegenerateResponse:
    if week_start.weekday() != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "week_start는 월요일이어야 합니다"},
        )
    if await request.app.state.container.postgres.get_report_record(couple_id, week_start) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": "리포트 주차를 찾을 수 없습니다"},
        )
    job_id = await request.app.state.container.postgres.create_report_job(couple_id, week_start)
    return RegenerateResponse(job_id=str(job_id))
