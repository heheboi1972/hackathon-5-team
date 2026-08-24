"""API_SPEC.md §7 liveness/readiness 엔드포인트."""

from fastapi import APIRouter, Request

from app.models.api import LiveResponse, ReadyResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request) -> ReadyResponse:
    provider = request.app.state.container.settings.ai_provider
    return ReadyResponse(
        postgres=True,
        qdrant=True,
        watsonx="mock" if provider == "mock" else False,
    )

