# 역할: ChatSupervisor 통합 테스트 — regex 선분기(LLM 0회) + intent별 툴 연결 (TASKS 3-6, TC-AGENT-005)
from __future__ import annotations

import asyncio
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.agents.chat_answer_agent import ChatAnswerAgent
from app.agents.chat_intent_agent import ChatIntentAgent
from app.agents.chat_supervisor import ChatSupervisor
from app.models.api import ChatRequest
from app.models.report import ChatAnswerOutput as _ChatAnswerOutput

KST = ZoneInfo("Asia/Seoul")


class _MockAI:
    provider_name = "mock"

    async def generate_json(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError("mock 모드는 LLM을 호출하지 않아야 합니다")


class _NeverCalled:
    """term_count/advice_request 는 LLM 0회여야 한다 — 호출되면 바로 실패시킨다."""

    async def run(self, *_args, **_kwargs):
        raise AssertionError("이 분기에서는 에이전트가 호출되면 안 됩니다")


def _supervisor(
    *,
    intent_agent=None,
    answer_agent=None,
    search_conversation=None,
    get_metrics=None,
    get_report=None,
    get_latest_report_week=None,
    count_term=None,
    top_terms=None,
):
    async def _default_search(*_args, **_kwargs):
        return []

    async def _default_metrics(*_args, **_kwargs):
        return _EMPTY_METRICS

    async def _default_report(*_args, **_kwargs):
        return None

    async def _default_latest_week(*_args, **_kwargs):
        return None

    async def _default_count(*_args, **_kwargs):
        return {"term": "", "total": 0, "matched_forms": [], "by_week": []}

    async def _default_top_terms(*_args, **_kwargs):
        return {"terms": []}

    return ChatSupervisor(
        intent_agent or ChatIntentAgent(_MockAI()),
        answer_agent or ChatAnswerAgent(_MockAI()),
        search_conversation=search_conversation or _default_search,
        get_metrics=get_metrics or _default_metrics,
        get_report=get_report or _default_report,
        get_latest_report_week=get_latest_report_week or _default_latest_week,
        count_term=count_term or _default_count,
        top_terms=top_terms or _default_top_terms,
    )


def _request(message: str, focus_range=None) -> ChatRequest:
    return ChatRequest(message=message, focus_range=focus_range)


# ChatResponse.metrics는 RangeMetrics/BaselineMetrics 전체 필드를 요구한다 — get_metrics 툴이
# 실제로 항상 채워주는 형태를 그대로 흉내낸다 (테스트가 임의 부분 dict를 넣으면 계약과 안 맞아 실패한다).
_METRIC = {"couple": 0.2, "mine": 0.1}


def _range_metrics_stub(comment: str = "평소와 비슷한 흐름으로 대화를 나눴어요.") -> dict:
    return {
        "range": {"question_rate": _METRIC, "reply_gap_median_min": _METRIC, "message_count": 10},
        "baseline": {
            "weeks": 4, "question_rate": _METRIC, "reply_gap_median_min": _METRIC,
            "message_count": 10.0,
        },
        "comment": comment,
    }


_EMPTY_METRICS = _range_metrics_stub()


# ---------------------------------------------------------------- term_count (LLM 0회)


def test_term_count_extracts_quoted_term_and_uses_count_term_tool():
    async def scenario():
        calls = []

        async def count_term(couple_id, term, *, start=None, end=None):
            calls.append(term)
            return {"term": term, "total": 44, "matched_forms": [{"form": term, "count": 44}], "by_week": []}

        supervisor = _supervisor(
            intent_agent=_NeverCalled(), answer_agent=_NeverCalled(), count_term=count_term
        )
        result = await supervisor.run(
            uuid4(), "a", _request("'사랑해' 몇 번 썼어?")
        )
        assert calls == ["사랑해"]
        assert result.intent == "term_count"
        assert "44번" in result.answer
        assert result.citations == []

    asyncio.run(scenario())


def test_term_count_falls_back_to_prefix_word_without_quotes():
    async def scenario():
        calls = []

        async def count_term(couple_id, term, *, start=None, end=None):
            calls.append(term)
            return {"term": term, "total": 3, "matched_forms": [{"form": term, "count": 3}], "by_week": []}

        supervisor = _supervisor(
            intent_agent=_NeverCalled(), answer_agent=_NeverCalled(), count_term=count_term
        )
        await supervisor.run(uuid4(), "a", _request("치킨 얼마나 자주 나왔어?"))
        assert calls == ["치킨"]

    asyncio.run(scenario())


def test_term_count_person_hint_adds_disclaimer_but_still_couple_sum():
    async def scenario():
        async def count_term(couple_id, term, *, start=None, end=None):
            return {"term": term, "total": 5, "matched_forms": [{"form": term, "count": 5}], "by_week": []}

        supervisor = _supervisor(
            intent_agent=_NeverCalled(), answer_agent=_NeverCalled(), count_term=count_term
        )
        result = await supervisor.run(uuid4(), "a", _request("내가 사랑해 몇 번 썼어?"))
        assert "누가 얼마나 썼는지는 알려드리지 않아요" in result.answer

    asyncio.run(scenario())


def test_term_count_zero_hits_is_honest_not_invented():
    async def scenario():
        async def count_term(couple_id, term, *, start=None, end=None):
            return {"term": term, "total": 0, "matched_forms": [], "by_week": []}

        supervisor = _supervisor(
            intent_agent=_NeverCalled(), answer_agent=_NeverCalled(), count_term=count_term
        )
        result = await supervisor.run(uuid4(), "a", _request("'우주여행' 몇 번 나왔어?"))
        assert "찾지 못했어요" in result.answer

    asyncio.run(scenario())


def test_term_count_pattern_matched_but_no_extractable_word_asks_again():
    async def scenario():
        supervisor = _supervisor(intent_agent=_NeverCalled(), answer_agent=_NeverCalled())
        result = await supervisor.run(uuid4(), "a", _request("몇 번 그랬어?"))
        assert result.intent == "term_count"
        assert "따옴표" in result.answer

    asyncio.run(scenario())


# ---------------------------------------------------------------- top_term (LLM 0회)


def test_top_term_regex_shortcut_never_calls_llm_and_uses_top_terms_tool():
    async def scenario():
        async def top_terms(couple_id, *, start=None, end=None, limit=5):
            assert limit == 5
            return {"terms": [{"term": "사랑해", "count": 12}, {"term": "치킨", "count": 5}]}

        supervisor = _supervisor(
            intent_agent=_NeverCalled(), answer_agent=_NeverCalled(), top_terms=top_terms
        )
        result = await supervisor.run(uuid4(), "a", _request("우리가 가장 많이 쓴 단어가 뭐야?"))
        assert result.intent == "top_term"
        assert "사랑해" in result.answer and "12번" in result.answer
        assert result.citations == []
        assert result.metrics is None

    asyncio.run(scenario())


def test_top_term_no_terms_is_honest_not_invented():
    async def scenario():
        supervisor = _supervisor(intent_agent=_NeverCalled(), answer_agent=_NeverCalled())
        result = await supervisor.run(uuid4(), "a", _request("제일 자주 쓰는 말이 뭐야?"))
        assert result.intent == "top_term"
        assert "없어요" in result.answer

    asyncio.run(scenario())


# ---------------------------------------------------------------- 상대 날짜 표현 (focus_range 보강)


def test_relative_date_phrase_is_parsed_into_focus_range_for_fact_query():
    """request.focus_range가 비어 있어도 "이번주" 같은 문구가 있으면 검색 범위를 좁힌다."""
    async def scenario():
        seen = {}

        async def search_conversation(couple_id, query, *, start=None, end=None, k=8):
            seen["start"], seen["end"] = start, end
            return []

        supervisor = _supervisor(search_conversation=search_conversation)
        await supervisor.run(uuid4(), "a", _request("이번주에 언제 만나기로 했었어?"))
        assert seen["start"] is not None and seen["end"] is not None
        assert seen["start"].weekday() == 0  # 월요일부터
        assert seen["start"] <= seen["end"]

    asyncio.run(scenario())


def test_explicit_focus_range_wins_over_relative_date_phrase():
    """request.focus_range가 이미 있으면 문구를 파싱해서 덮어쓰지 않는다."""
    async def scenario():
        seen = {}

        async def search_conversation(couple_id, query, *, start=None, end=None, k=8):
            seen["start"], seen["end"] = start, end
            return []

        supervisor = _supervisor(search_conversation=search_conversation)
        start, end = datetime(2026, 1, 1, tzinfo=KST), datetime(2026, 1, 7, tzinfo=KST)
        await supervisor.run(
            uuid4(), "a",
            _request("이번주에 언제 만나기로 했었어?", focus_range={"start": start, "end": end}),
        )
        assert seen["start"] == start and seen["end"] == end

    asyncio.run(scenario())


def test_relative_date_phrase_has_no_effect_when_absent():
    """상대 날짜 표현이 문장에 없으면 여전히 기간 제한 없이(None) 검색한다 — 기존 동작 보존."""
    async def scenario():
        seen = {}

        async def search_conversation(couple_id, query, *, start=None, end=None, k=8):
            seen["start"], seen["end"] = start, end
            return []

        supervisor = _supervisor(search_conversation=search_conversation)
        await supervisor.run(uuid4(), "a", _request("우리 언제 제주도 얘기했지?"))
        assert seen["start"] is None and seen["end"] is None

    asyncio.run(scenario())


# ------------------------------------------- advice_request (감지 LLM 0회, 안내문 생성 LLM 1회)
#
# 2026-08-27: 안내 문구가 고정 문자열 → chat_answer 에이전트의 LLM 생성으로 바뀌었다(윤아 요청).
# 그래도 "이 메시지가 advice_request인지 판단하는 것" 자체은 여전히 regex/LLM-classifier가
# 결정론적으로 하므로, intent_agent(분류기)는 아래 두 테스트에서 여전히 호출되면 안 된다 —
# 검증 대상이 바뀐 건 answer_agent(문구 생성) 쪽이다.


def test_advice_request_regex_shortcut_never_calls_intent_classifier():
    async def scenario():
        supervisor = _supervisor(intent_agent=_NeverCalled())
        result = await supervisor.run(uuid4(), "a", _request("우리 어떻게 화해해야 할까?"))
        assert result.intent == "advice_request"
        assert result.answer is None
        assert result.redirect
        assert result.citations == []
        assert result.metrics is None

    asyncio.run(scenario())


def test_advice_mixed_with_other_topic_still_wins_per_boundary_rule():
    """chat_intent.md 경계 규칙: 조언 요청이 섞이면 advice_request 우선."""
    async def scenario():
        supervisor = _supervisor(intent_agent=_NeverCalled())
        result = await supervisor.run(
            uuid4(), "a", _request("우리 대화 패턴 보고 어떻게 해야 할지 조언해줘")
        )
        assert result.intent == "advice_request"

    asyncio.run(scenario())


def test_advice_request_redirect_comes_from_answer_agent():
    """2026-08-27: redirect 문구는 이제 chat_supervisor가 직접 안 만들고 answer_agent.run()이
    돌려준 값을 그대로 옮긴다 — 이걸 가짜 answer_agent로 확인한다(고정 문구가 아님을 검증)."""
    async def scenario():
        calls: list[tuple[str, dict]] = []

        class _FakeAnswerAgent:
            async def run(self, intent, payload, **_kwargs):
                calls.append((intent, payload))
                return _ChatAnswerOutput(answer="테스트용 안내 문구입니다.", citations=[])

        supervisor = _supervisor(intent_agent=_NeverCalled(), answer_agent=_FakeAnswerAgent())
        result = await supervisor.run(uuid4(), "a", _request("우리 헤어지는 게 나을까?"))

        assert calls and calls[0][0] == "advice_request"
        assert calls[0][1]["message"] == "우리 헤어지는 게 나을까?"
        assert result.redirect == "테스트용 안내 문구입니다."
        assert result.answer is None

    asyncio.run(scenario())


def test_advice_request_reached_via_intent_classifier_when_regex_misses():
    """감지 방식이 두 가지라(선분기 regex / chat_intent LLM 분류) 후자 경로도 같은 핸들러로
    간다는 걸 확인한다. "괜찮은 관계야?"는 supervisor의 ADVICE_PATTERN(...관계일까 필요)엔
    안 걸리지만, mock ChatIntentAgent의 힌트(...관계 만 있어도 매치)엔 걸린다."""
    async def scenario():
        supervisor = _supervisor()
        result = await supervisor.run(uuid4(), "a", _request("우리 지금 괜찮은 관계야?"))
        assert result.intent == "advice_request"
        assert result.redirect

    asyncio.run(scenario())


# ---------------------------------------------------------------- fact_query


def test_fact_query_grounds_answer_in_search_results():
    async def scenario():
        async def search_conversation(couple_id, query, *, start=None, end=None, k=8):
            assert k == 8
            return [
                {
                    "session_id": 10,
                    "at": datetime(2026, 8, 24, 21, tzinfo=KST),
                    "sender": "a",
                    "snippet": "오늘 하루는 어땠어",
                    "score": 0.9,
                }
            ]

        supervisor = _supervisor(search_conversation=search_conversation)
        result = await supervisor.run(
            uuid4(), "a", _request("우리 언제 처음 자기야라고 불렀지?")
        )
        assert result.intent == "fact_query"
        assert result.citations
        assert result.citations[0].session_id == 10
        assert result.metrics is None

    asyncio.run(scenario())


def test_fact_query_no_search_results_is_honest():
    async def scenario():
        supervisor = _supervisor()  # 기본 search_conversation은 빈 리스트
        result = await supervisor.run(
            uuid4(), "a", _request("우리 언제 처음 자기야라고 불렀지?")
        )
        assert result.intent == "fact_query"
        assert result.citations == []
        assert "찾지 못했어요" in result.answer

    asyncio.run(scenario())


# ---------------------------------------------------------------- metric_query


def test_metric_query_response_metrics_come_from_tool_not_llm():
    """P-2: 숫자는 코드가 만든다 — LLM이 뭘 돌려주든 supervisor는 툴의 원본 값을 붙인다."""
    async def scenario():
        tool_result = _range_metrics_stub("지난 8주보다 답장이 많이 느려졌어요")

        async def get_metrics(couple_id, me, *, focus_range=None):
            return tool_result

        supervisor = _supervisor(get_metrics=get_metrics)
        result = await supervisor.run(uuid4(), "a", _request("요즘 답장 느려졌어?"))
        assert result.intent == "metric_query"
        assert result.metrics.model_dump(mode="json") == tool_result
        assert result.answer == tool_result["comment"]

    asyncio.run(scenario())


def test_metric_query_passes_focus_range_through_to_tool():
    async def scenario():
        seen = {}

        async def get_metrics(couple_id, me, *, focus_range=None):
            seen["focus_range"] = focus_range
            return _EMPTY_METRICS

        supervisor = _supervisor(get_metrics=get_metrics)
        start, end = datetime(2026, 8, 1, tzinfo=KST), datetime(2026, 8, 7, tzinfo=KST)
        await supervisor.run(
            uuid4(), "a", _request("요즘 답장 느려졌어?", focus_range={"start": start, "end": end})
        )
        assert seen["focus_range"] == (start, end)

    asyncio.run(scenario())


# ---------------------------------------------------------------- report_query


def test_report_query_uses_latest_generated_week_when_no_focus_range():
    async def scenario():
        seen = {}

        async def get_latest_report_week(couple_id):
            return date(2026, 8, 17)

        async def get_report(couple_id, me, week_start):
            seen["week_start"] = week_start
            return {
                "week_start": week_start, "status": "generated",
                "report": {"highlights": [{"observation": "요즘 대화가 짧게 끝나는 편이에요"}]},
            }

        supervisor = _supervisor(
            get_latest_report_week=get_latest_report_week, get_report=get_report
        )
        result = await supervisor.run(uuid4(), "a", _request("저번 리포트에서 뭐라고 나왔지?"))
        assert seen["week_start"] == date(2026, 8, 17)
        assert result.intent == "report_query"
        assert "짧게 끝나는" in result.answer

    asyncio.run(scenario())


def test_report_query_pending_or_missing_is_honest_not_invented():
    async def scenario():
        supervisor = _supervisor()  # get_latest_report_week -> None, get_report 안 불림
        result = await supervisor.run(uuid4(), "a", _request("저번 리포트에서 뭐라고 나왔지?"))
        assert "준비되지" in result.answer

    asyncio.run(scenario())


# ---------------------------------------------------------------- other


def test_other_intent_redirects_to_supported_topics():
    async def scenario():
        supervisor = _supervisor(answer_agent=_NeverCalled())
        result = await supervisor.run(uuid4(), "a", _request("오늘 날씨 어때?"))
        assert result.intent == "other"
        assert result.citations == []
        assert result.redirect is None

    asyncio.run(scenario())


# ---------------------------------------------------------------- 라우터 배선 (DB 없이, current_member만 오버라이드)


def test_chat_router_calls_container_supervisor_end_to_end():
    """routers/chat.py가 request.app.state.container.chat_supervisor 를 실제로 호출하고
    ChatResponse 계약대로 직렬화하는지 — 유닛 테스트로는 안 잡히는 배선(container.py) 확인."""
    from types import SimpleNamespace
    from uuid import UUID

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.deps import current_member
    from app.routers import chat as chat_router

    app = FastAPI()
    app.include_router(chat_router.router)
    app.state.container = SimpleNamespace(chat_supervisor=_supervisor())
    app.dependency_overrides[current_member] = lambda: "a"

    couple_id = UUID("11111111-1111-1111-1111-111111111111")
    response = TestClient(app).post(
        f"/api/couples/{couple_id}/chat", json={"message": "오늘 날씨 어때?"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] == "other"
    assert body["trace_id"]
