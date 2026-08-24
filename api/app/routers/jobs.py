"""잡 진행률 조회 API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..deps import AuthenticatedUser, current_user
from ..models.api import JobProgress, JobResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
) -> JobResponse:
    row = await request.app.state.container.postgres.get_job_for_user(
        job_id, user.user_id
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "잡을 찾을 수 없습니다"},
        )
    return JobResponse(
        job_id=str(row["job_id"]),
        kind=row["kind"],
        status=row["status"],
        progress=JobProgress(
            total=row["total"], done=row["done"], failed=row["failed"]
        ),
        current_week=row["current_week"],
    )
