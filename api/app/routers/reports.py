# 역할: FR-004 리포트 — GET /api/couples/{id}/reports/{week}, POST regenerate (참조: API_SPEC §4.2~4.3)
# 스캐폴딩 스텁: mock/report_stored.json(저장형)을 투영해 반환. 실제 조회·재생성 큐는 TODO(윤석)
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_report 만 호출 (ISSUE B3).
# TODO(윤석): load_mock("report_stored") 를 reports + weekly_metrics + weekly_terms 조회로 교체.
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import current_member
from ..models.api import RegenerateResponse, ReportResponse, Who
from ..services.projection import build_report
from ..utils.json_utils import load_mock

router = APIRouter(prefix="/api/couples", tags=["reports"])


@router.get("/{couple_id}/reports/{week_start}", response_model=ReportResponse)
async def get_report(
    couple_id: str,
    week_start: date,
    me: Who = Depends(current_member),
) -> ReportResponse:
    if week_start.weekday() != 0:  # 월요일만 허용 (API_SPEC §4.2)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "VALIDATION_ERROR", "message": "week_start는 월요일이어야 합니다"},
        )
    return build_report(load_mock("report_stored"), me, week_start)


@router.post(
    "/{couple_id}/reports/{week_start}/regenerate",
    response_model=RegenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate(couple_id: str, week_start: date) -> RegenerateResponse:
    return RegenerateResponse(job_id=str(uuid.uuid4()))
