"""FR-006 대화 검색 챗봇 API Mock 라우터."""

from uuid import uuid4

from fastapi import APIRouter

from app.deps import CurrentMember
from app.models.api import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/couples/{couple_id}", tags=["chat"])
ADVICE_REDIRECT = (
    "이 챗봇은 대화 기록을 찾아주는 도구예요. 관계가 어떤지는 저도 판단하지 않아요. "
    "대신 요즘 대화가 어땠는지는 같이 볼 수 있어요."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(couple_id: str, payload: ChatRequest, _: CurrentMember) -> ChatResponse:
    del couple_id
    message = payload.message
    trace_id = str(uuid4())
    if any(term in message for term in ("괜찮은 거야", "헤어", "관계가 어때")):
        return ChatResponse(
            intent="advice_request",
            answer=None,
            citations=[],
            redirect=ADVICE_REDIRECT,
            trace_id=trace_id,
        )
    if any(term in message for term in ("몇 번", "몇 회", "얼마나 자주")):
        return ChatResponse(
            intent="term_count",
            answer="Mock 모드에서는 해당 표현이 전체 대화에서 3번 나왔어요.",
            citations=[],
            redirect=None,
            trace_id=trace_id,
        )
    return ChatResponse(
        intent="fact_query",
        answer="Mock 모드의 대화 기록 응답입니다.",
        citations=[],
        redirect=None,
        trace_id=trace_id,
    )

