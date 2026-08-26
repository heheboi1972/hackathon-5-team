# 역할: FR-006 대화 검색 챗봇 — POST /api/couples/{id}/chat (참조: API_SPEC §6)
# 라우터는 chat_supervisor만 호출한다 — intent 분기·툴 호출·인용 강제는 전부 supervisor 책임.
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ..deps import current_member
from ..models.api import ChatRequest, ChatResponse, Who

router = APIRouter(prefix="/api/couples", tags=["chat"])


@router.post("/{couple_id}/chat", response_model=ChatResponse)
async def chat(
    couple_id: UUID,
    body: ChatRequest,
    request: Request,
    me: Who = Depends(current_member),
) -> ChatResponse:
    supervisor = request.app.state.container.chat_supervisor
    return await supervisor.run(couple_id, me, body)
