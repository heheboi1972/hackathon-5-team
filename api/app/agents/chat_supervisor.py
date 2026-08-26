# 역할: 챗봇 수퍼바이저 — intent 분류 → 툴 → 인용 강제 → 리다이렉트 (참조: FR-006, API_SPEC §6.1, TRD §5.3)
# 분기 순서 (LLM 호출을 줄이려면 결정론 분기를 먼저):
#   1. term_count    : regex 로 "X 몇 번/몇 회/얼마나 자주" 를 잡아 단어 추출 → count_term 툴 → 템플릿 답변 (LLM 0회)
#   2. advice_request: 키워드 regex → 고정 리다이렉트 문구 (LLM 0회)
#   3. 나머지        : chat_intent 로 분류 → 그에 맞는 툴 → chat_answer 로 1회 호출
from __future__ import annotations

import re
from datetime import date
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from ..models.api import ChatRequest, ChatResponse, Who
from ..services.metrics import week_start_of
from ..services.term_search import format_answer

# term_count 선분기용 패턴 (prompts/chat_intent.md 와 같은 규칙)
COUNT_PATTERN = re.compile(r"(몇\s*번|몇\s*회|얼마나\s*자주)")
QUOTED_TERM = re.compile(
    r"['\"‘’“”]([^'\"‘’“”]{1,20})['\"‘’“”]"
)
# "내가/네가/쟤가 몇 번" — 사람을 지목한 질문이어도 합산으로만 답하고 안내 문구를 덧붙인다
PERSON_HINT = re.compile(r"(내가|제가|나는|너가|네가|쟤가|걔가|상대(방)?가)")
# advice_request 사전 분기 (chat_intent.md "경계 규칙": 조언 요청이 섞이면 최우선)
ADVICE_PATTERN = re.compile(
    r"(어떻게\s*해야|어떡해야|나을까|괜찮은\s*관계일까|화해|헤어지)"
)

_ADVICE_REDIRECT = (
    "이 챗봇은 대화 기록을 찾아주는 도구예요. 관계가 어떤지는 저도 판단하지 않아요. "
    "대신 요즘 대화가 어땠는지는 같이 볼 수 있어요."
)
_OTHER_ANSWER = "대화 기록·지표·리포트에 대해 물어봐 주세요."
_NO_TERM_ANSWER = "어떤 단어를 세어볼까요? 궁금한 단어를 따옴표로 감싸서 다시 물어봐 주세요."


def _extract_term(message: str) -> str | None:
    """따옴표 안이 있으면 우선, 없으면 패턴 앞 어절 (chat_intent.md 규칙)."""
    quoted = QUOTED_TERM.search(message)
    if quoted:
        return quoted.group(1)
    match = COUNT_PATTERN.search(message)
    if not match:
        return None
    prefix = message[: match.start()].strip()
    if not prefix:
        return None
    return prefix.split()[-1]


def _history_payload(request: ChatRequest) -> list[dict[str, str]]:
    return [turn.model_dump(mode="json") for turn in request.history]


def _focus_range_payload(request: ChatRequest) -> dict[str, str] | None:
    return request.focus_range.model_dump(mode="json") if request.focus_range else None


class ChatSupervisor:
    def __init__(
        self,
        intent_agent: Any,
        answer_agent: Any,
        *,
        search_conversation: Callable[..., Awaitable[list[dict[str, Any]]]],
        get_metrics: Callable[..., Awaitable[dict[str, Any]]],
        get_report: Callable[..., Awaitable[dict[str, Any] | None]],
        get_latest_report_week: Callable[[UUID], Awaitable[date | None]],
        count_term: Callable[..., Awaitable[dict[str, Any]]],
    ):
        self.intent_agent = intent_agent
        self.answer_agent = answer_agent
        self.search_conversation = search_conversation
        self.get_metrics = get_metrics
        self.get_report = get_report
        self.get_latest_report_week = get_latest_report_week
        self.count_term = count_term

    async def run(self, couple_id: UUID, me: Who, request: ChatRequest) -> ChatResponse:
        trace_id = str(uuid4())
        message = request.message

        # 1. term_count — LLM 0회
        if COUNT_PATTERN.search(message):
            return await self._term_count(couple_id, message, request, trace_id)

        # 2. advice_request — LLM 0회 (chat_intent.md 경계 규칙: 조언이 섞이면 최우선)
        if ADVICE_PATTERN.search(message):
            return self._advice(trace_id)

        # 3. 나머지 — intent 분류 1회 호출
        intent_out = await self.intent_agent.run(
            {
                "message": message,
                "focus_range": _focus_range_payload(request),
                "history": _history_payload(request),
            }
        )

        if intent_out.intent == "advice_request":
            return self._advice(trace_id)
        if intent_out.intent == "other":
            return ChatResponse(
                intent="other", answer=_OTHER_ANSWER, citations=[],
                redirect=None, trace_id=trace_id, metrics=None,
            )
        if intent_out.intent == "fact_query":
            return await self._fact_query(couple_id, message, request, trace_id)
        if intent_out.intent == "metric_query":
            return await self._metric_query(couple_id, me, message, request, trace_id)
        return await self._report_query(couple_id, me, message, request, trace_id)

    def _advice(self, trace_id: str) -> ChatResponse:
        return ChatResponse(
            intent="advice_request", answer=None, citations=[],
            redirect=_ADVICE_REDIRECT, trace_id=trace_id, metrics=None,
        )

    async def _term_count(
        self, couple_id: UUID, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        term = _extract_term(message)
        if term is None:
            # regex 는 걸렸는데(패턴 매치) 대상 단어를 못 뽑음 — 지어내지 않고 다시 물어본다
            # (chat_intent.md: "regex 가 실패할 때만 LLM 이 단어를 뽑는다"의 LLM 폴백은 TODO)
            return ChatResponse(
                intent="term_count", answer=_NO_TERM_ANSWER, citations=[],
                redirect=None, trace_id=trace_id, metrics=None,
            )
        start = request.focus_range.start if request.focus_range else None
        end = request.focus_range.end if request.focus_range else None
        result = await self.count_term(couple_id, term, start=start, end=end)
        answer = format_answer(result, asked_about_person=bool(PERSON_HINT.search(message)))
        return ChatResponse(
            intent="term_count", answer=answer, citations=[],
            redirect=None, trace_id=trace_id, metrics=None,
        )

    async def _fact_query(
        self, couple_id: UUID, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        start = request.focus_range.start if request.focus_range else None
        end = request.focus_range.end if request.focus_range else None
        candidates = await self.search_conversation(
            couple_id, message, start=start, end=end, k=8
        )
        payload = {
            "message": message,
            "focus_range": _focus_range_payload(request),
            "history": _history_payload(request),
            "evidence_candidates": candidates,
        }
        output = await self.answer_agent.run("fact_query", payload, candidates=candidates)
        return ChatResponse(
            intent="fact_query", answer=output.answer,
            citations=[c.model_dump(mode="json") for c in output.citations],
            redirect=None, trace_id=trace_id, metrics=None,
        )

    async def _metric_query(
        self, couple_id: UUID, me: Who, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        focus = (
            (request.focus_range.start, request.focus_range.end)
            if request.focus_range
            else None
        )
        metrics_result = await self.get_metrics(couple_id, me, focus_range=focus)
        payload = {
            "message": message,
            "focus_range": _focus_range_payload(request),
            "history": _history_payload(request),
            "metrics": metrics_result,
        }
        output = await self.answer_agent.run("metric_query", payload)
        return ChatResponse(
            intent="metric_query", answer=output.answer, citations=[],
            redirect=None, trace_id=trace_id, metrics=metrics_result,
        )

    async def _report_query(
        self, couple_id: UUID, me: Who, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        if request.focus_range is not None:
            target_week = week_start_of(request.focus_range.start.date())
        else:
            target_week = await self.get_latest_report_week(couple_id)
        report = await self.get_report(couple_id, me, target_week) if target_week else None
        payload = {
            "message": message,
            "focus_range": _focus_range_payload(request),
            "history": _history_payload(request),
            "report": report["report"] if report else None,
        }
        output = await self.answer_agent.run("report_query", payload)
        return ChatResponse(
            intent="report_query", answer=output.answer, citations=[],
            redirect=None, trace_id=trace_id, metrics=None,
        )
