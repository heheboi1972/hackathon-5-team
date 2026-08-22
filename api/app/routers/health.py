# 역할: 헬스체크 — GET /health/live, /health/ready (참조: API_SPEC §7)
from fastapi import APIRouter, Request, Response, status

from ..models.api import HealthLiveResponse, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthLiveResponse)
async def live() -> HealthLiveResponse:
    return HealthLiveResponse()


@router.get("/ready", response_model=HealthReadyResponse)
async def ready(request: Request, response: Response) -> HealthReadyResponse:
    container = getattr(request.app.state, "container", None)
    pg = qd = False
    watsonx: bool | str = False
    if container is not None:
        pg = await container.postgres_ok()
        qd = await container.qdrant_ok()
        watsonx = "mock" if container.ai.provider_name == "mock" else True
    if not (pg and qd):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthReadyResponse(postgres=pg, qdrant=qd, watsonx=watsonx)
