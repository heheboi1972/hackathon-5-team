# 역할: FR-006 대화 검색 챗봇 — POST /api/couples/{id}/chat (참조: API_SPEC §6)
# 스캐폴딩 스텁: 키워드로 advice/fact 분기해 mock JSON 반환. chat_supervisor 연결은 TODO(윤석)
import uuid

from fastapi import APIRouter

from ..models.api import ChatRequest, ChatResponse
from ..utils.json_utils import load_mock

router = APIRouter(prefix="/api/couples", tags=["chat"])

_ADVICE_HINTS = ("어떻게", "어떡", "조언", "화해", "고치", "문제야", "해야 할까", "해야할까")


@router.post("/{couple_id}/chat", response_model=ChatResponse)
async def chat(couple_id: str, body: ChatRequest) -> ChatResponse:
    key = "chat_advice" if any(h in body.message for h in _ADVICE_HINTS) else "chat_fact"
    data = load_mock(key)
    data["trace_id"] = str(uuid.uuid4())
    return ChatResponse.model_validate(data)
