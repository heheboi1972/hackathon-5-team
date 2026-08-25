# 역할: FR-003 타임라인 — GET /api/couples/{id}/timeline (참조: API_SPEC §4.1)
# 라우터는 응답 모델을 직접 만들지 않는다 — services.projection.build_timeline 만 호출 (ISSUE B3).
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from ..deps import current_member
from ..models.api import TimelineResponse, Who
from ..services.projection import build_timeline

router = APIRouter(prefix="/api/couples", tags=["timeline"])


@router.get("/{couple_id}/timeline", response_model=TimelineResponse)
async def timeline(
    couple_id: UUID,
    request: Request,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    me: Who = Depends(current_member),
) -> TimelineResponse:
    stored_weeks = await request.app.state.container.postgres.get_timeline(
        couple_id, from_=from_, to=to
    )
    return build_timeline(stored_weeks, me)
