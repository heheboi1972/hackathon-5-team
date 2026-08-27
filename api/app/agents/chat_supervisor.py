# 역할: 챗봇 수퍼바이저 — intent 분류 → 툴 → 인용 강제 → 리다이렉트 (참조: FR-006, API_SPEC §6.1, TRD §5.3)
# 분기 순서 (LLM 호출을 줄이려면 결정론 분기를 먼저):
#   1. top_term      : regex 로 "가장/제일 많이 쓴 단어" 류를 잡아 → top_terms 툴 → 템플릿 답변 (LLM 0회)
#   2. term_count    : regex 로 "X 몇 번/몇 회/얼마나 자주" 를 잡아 단어 추출 → count_term 툴 → 템플릿 답변 (LLM 0회)
#   3. advice_request: 키워드 regex/LLM-classifier로 감지(감지 자체는 여전히 결정론적) → chat_answer
#      에 LLM 1회 호출해 안내 문구를 생성(2026-08-27부터, 이전엔 고정 문구였음) → banned_patterns.txt로
#      한 번 더 스캐닝해서 조언/판단 표현이 섞이면 고정 문구로 폴백 (chat_answer_agent.py 참고)
#   4. 나머지        : chat_intent 로 분류 → 그에 맞는 툴 → chat_answer 로 1회 호출
#
# focus_range 보강 (2026-08-27): 프론트가 아직 focus_range를 안 채워 보내는 케이스가 있어
# (request.focus_range가 항상 None), "이번주"/"저번에" 같은 상대 날짜 표현이 그냥 검색
# 문장 텍스트로만 취급돼 못 찾는 문제가 있었다 — _effective_range()가 request.focus_range가
# 없을 때만 메시지에서 상대 날짜를 파싱해 보충한다 (fact_query/metric_query/report_query/
# term_count 공통).
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from ..models.api import ChatRequest, ChatResponse, Who
from ..services.metrics import week_start_of
from ..services.term_search import format_answer, format_top_terms_answer

KST = timezone(timedelta(hours=9))

# top_term 선분기용 패턴 — "가장/제일 많이 쓴 단어" 류. 특정 단어를 짚는 term_count와 달리
# 순위 자체를 묻는 질문이라 별도로 둔다 (chat_intent.md/LLM은 아직 이 케이스를 모른다).
TOP_TERM_PATTERN = re.compile(
    r"(가장|제일)\s*(많이|자주)\s*(쓴|쓰는|사용한|사용하는)?\s*(단어|말|표현)"
)

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

# 고정 안내 문구(ADVICE_FALLBACK_TEXT)는 chat_answer_agent.py로 옮김 — 그쪽이 mock/안전-폴백
# 양쪽에서 실제로 이 문구를 쓰는 소스오브트루스라, 여기 supervisor에는 더 이상 안 둔다.
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


def _last_month_range(today: date) -> tuple[date, date]:
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_of_prev_month.replace(day=1), last_of_prev_month


# 상대 날짜 표현 → (start_date, end_date) 리졸버. 구체적인 표현을 먼저 검사하도록 나열 순서를
# 신경 쓸 필요는 없다 — 정규식이 서로 겹치지 않는다("이번주"는 "저번/지난 주"와 매치되지 않음).
_RELATIVE_RANGE_PATTERNS: list[tuple[re.Pattern[str], Callable[[date], tuple[date, date]]]] = [
    (re.compile(r"오늘"), lambda today: (today, today)),
    (re.compile(r"어제"), lambda today: (today - timedelta(days=1), today - timedelta(days=1))),
    (
        re.compile(r"(저번|지난)\s*주"),
        lambda today: (
            week_start_of(today) - timedelta(days=7),
            week_start_of(today) - timedelta(days=1),
        ),
    ),
    (re.compile(r"이번\s*주"), lambda today: (week_start_of(today), today)),
    (re.compile(r"(저번|지난)\s*달"), lambda today: _last_month_range(today)),
    (re.compile(r"이번\s*달"), lambda today: (today.replace(day=1), today)),
]


def _parse_relative_range(message: str, *, today: date) -> tuple[datetime, datetime] | None:
    """메시지 속 "이번주"/"어제" 같은 상대 날짜 표현을 KST 하루 경계 기준 datetime 범위로 바꾼다.
    못 찾으면 None — 호출부는 그러면 그냥 기간 제한 없이 검색한다(기존 동작 그대로 유지)."""
    for pattern, resolver in _RELATIVE_RANGE_PATTERNS:
        if pattern.search(message):
            start_date, end_date = resolver(today)
            start = datetime.combine(start_date, time.min, tzinfo=KST)
            end = datetime.combine(end_date, time.max, tzinfo=KST)
            return start, end
    return None


def _effective_range(request: ChatRequest, message: str) -> tuple[datetime, datetime] | None:
    """request.focus_range(프론트가 명시적으로 좁힌 범위)가 최우선이고, 그게 없을 때만
    메시지 텍스트에서 상대 날짜 표현을 파싱해 보충한다."""
    if request.focus_range:
        return request.focus_range.start, request.focus_range.end
    return _parse_relative_range(message, today=datetime.now(KST).date())


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
        top_terms: Callable[..., Awaitable[dict[str, Any]]],
    ):
        self.intent_agent = intent_agent
        self.answer_agent = answer_agent
        self.search_conversation = search_conversation
        self.get_metrics = get_metrics
        self.get_report = get_report
        self.get_latest_report_week = get_latest_report_week
        self.count_term = count_term
        self.top_terms = top_terms

    async def run(self, couple_id: UUID, me: Who, request: ChatRequest) -> ChatResponse:
        trace_id = str(uuid4())
        message = request.message

        # 1. top_term — LLM 0회
        if TOP_TERM_PATTERN.search(message):
            return await self._top_term(couple_id, message, request, trace_id)

        # 2. term_count — LLM 0회
        if COUNT_PATTERN.search(message):
            return await self._term_count(couple_id, message, request, trace_id)

        # 3. advice_request — 감지는 LLM 0회(regex), 안내 문구 생성은 LLM 1회 (chat_intent.md
        # 경계 규칙: 조언이 섞이면 최우선)
        if ADVICE_PATTERN.search(message):
            return await self._advice(message, request, trace_id)

        # 4. 나머지 — intent 분류 1회 호출
        intent_out = await self.intent_agent.run(
            {
                "message": message,
                "focus_range": _focus_range_payload(request),
                "history": _history_payload(request),
            }
        )

        if intent_out.intent == "advice_request":
            return await self._advice(message, request, trace_id)
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

    async def _advice(
        self, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        """안내 문구는 chat_answer 에이전트가 LLM으로 생성한다(2026-08-27, 윤아 요청).
        안전 폴백(banned_patterns.txt 스캔·mock provider)은 chat_answer_agent.py의
        _enforce_advice_safety가 처리하므로 여기서는 결과를 그대로 redirect에 싣기만 한다."""
        output = await self.answer_agent.run(
            "advice_request",
            {"message": message, "history": _history_payload(request)},
        )
        return ChatResponse(
            intent="advice_request", answer=None, citations=[],
            redirect=output.answer, trace_id=trace_id, metrics=None,
        )

    async def _top_term(
        self, couple_id: UUID, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        start, end = _effective_range(request, message) or (None, None)
        result = await self.top_terms(couple_id, start=start, end=end, limit=5)
        answer = format_top_terms_answer(result)
        return ChatResponse(
            intent="top_term", answer=answer, citations=[],
            redirect=None, trace_id=trace_id, metrics=None,
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
        start, end = _effective_range(request, message) or (None, None)
        result = await self.count_term(couple_id, term, start=start, end=end)
        answer = format_answer(result, asked_about_person=bool(PERSON_HINT.search(message)))
        return ChatResponse(
            intent="term_count", answer=answer, citations=[],
            redirect=None, trace_id=trace_id, metrics=None,
        )

    async def _fact_query(
        self, couple_id: UUID, message: str, request: ChatRequest, trace_id: str
    ) -> ChatResponse:
        start, end = _effective_range(request, message) or (None, None)
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
        focus = _effective_range(request, message)
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
        effective = _effective_range(request, message)
        if effective is not None:
            target_week = week_start_of(effective[0].date())
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
