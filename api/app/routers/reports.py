# 역할: FR-004 리포트 — GET /api/couples/{id}/reports/{week}, POST regenerate (참조: API_SPEC §4.2~4.3)
# 스캐폴딩 스텁: mock/report_generated.json 반환. 실제 조회·재생성 큐는 TODO(윤석)
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status

from ..models.api import RegenerateResponse, ReportResponse
from ..utils.json_utils import load_mock

router = APIRouter(prefix="/api/couples", tags=["reports"])


@router.get("/{couple_id}/reports/{week_start}", response_model=ReportResponse)
async def get_report(couple_id: str, week_start: date) -> ReportResponse:
    if week_start.weekday() != 0:  # 월요일만 허용 (API_SPEC §4.2)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "week_start는 월요일이어야 합니다"},
        )
    data = load_mock("report_generated")
    data["week_start"] = week_start.isoformat()
    return ReportResponse.model_validate(data)


@router.post(
    "/{couple_id}/reports/{week_start}/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate(couple_id: str, week_start: date) -> RegenerateResponse:
    return RegenerateResponse(job_id=str(uuid.uuid4()))
