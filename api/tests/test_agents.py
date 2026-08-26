"""TC-AGENT-001~004 에이전트 계약 자동화."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from functools import partial
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.agents.base import AgentOutputError
from app.agents.chat_answer_agent import ChatAnswerAgent, NO_RECORD_TEXT
from app.agents.chat_intent_agent import ChatIntentAgent
from app.agents.interpret_agent import InterpretAgent
from app.agents.report_supervisor import (
    SELECTABLE_AGENT_METRICS,
    _outlier_signals,
)
from app.agents.safety_agent import SafetyAgent
from app.agents.select_agent import SelectAgent
from app.agents.suggest_agent import SuggestAgent
from app.models.report import InterpretedHighlight, SelectOutput
from app.services.knowledge import Knowledge, load_knowledge
from app.tools.get_suggestion_templates import get_suggestion_templates
from app.tools.search_knowledge import search_knowledge

KST = ZoneInfo("Asia/Seoul")
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "data" / "knowledge"


class _MockAI:
    provider_name = "mock"

    async def generate_json(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError("mock 에이전트는 LLM을 호출하지 않아야 합니다")


class _InvalidAI:
    provider_name = "watsonx"

    def __init__(self):
        self.calls = 0

    async def generate_json(self, *_args, **_kwargs):
        self.calls += 1
        return {"invalid": True}


def _contains_private_key(node) -> bool:
    if isinstance(node, dict):
        if {"who", "a", "b"} & set(node):
            return True
        return any(_contains_private_key(value) for value in node.values())
    if isinstance(node, list):
        return any(_contains_private_key(value) for value in node)
    return False


def test_interpretation_clause_over_40_chars_rejected():
    """ISSUE C9: 절 형식(마침표·종결어미 없음)에 이어 길이 상한도 Pydantic 단에서 막는다.

    generate_validated()의 model_validate() 호출 경로에서 터지므로 실 LLM 출력에도
    똑같이 걸려 1회 재요청으로 이어진다(TRD §1) — 목 데이터만 보는 렌더 테스트로는
    못 잡는 경로라 여기서 직접 검증한다."""
    too_long = "이" * 41  # 종결어미·마침표는 없지만 40자를 넘는 절
    with pytest.raises(ValueError, match="40자"):
        InterpretedHighlight(
            observation="관찰 문장",
            interpretations=[too_long, "짧은 절이었을 수도"],
        )
    # 정확히 40자는 통과해야 한다 (상한 자체이지 그보다 짧은 값이 아님)
    exactly_40 = "이" * 40
    InterpretedHighlight(
        observation="관찰 문장",
        interpretations=[exactly_40, "짧은 절이었을 수도"],
    )


def test_select_agent_filters_caps_balances_and_validates_schema():
    async def scenario():
        agent = SelectAgent(_MockAI())
        empty = await agent.run(
            {
                "metrics": [
                    {
                        "metric": "question_rate",
                        "direction": "down",
                        "magnitude": "clear",
                        "comparable": False,
                    }
                ]
            }
        )
        assert empty.candidates == []

        output = await agent.run(
            {
                "metrics": [
                    {"metric": f"metric_{i}", "direction": "up", "magnitude": "clear"}
                    for i in range(5)
                ],
                "outliers": [
                    {
                        "metric": "positive_flow",
                        "direction": "up",
                        "magnitude": "clear",
                        "outlier_ref": "positive-1",
                        "sentiment": "positive",
                    },
                    {
                        "metric": "negative_flow",
                        "direction": "down",
                        "magnitude": "clear",
                        "outlier_ref": "negative-1",
                        "sentiment": "negative",
                    },
                ],
            }
        )
        assert len(output.candidates) == 3
        assert {item.outlier_ref for item in output.candidates} >= {
            "positive-1",
            "negative-1",
        }
        dumped = output.model_dump()
        assert SelectOutput.model_validate(dumped) == output
        assert not _contains_private_key(dumped)

    asyncio.run(scenario())


def _conversation_tool(couple_id, query, start=None, end=None, k=8):
    assert couple_id and query and k == 8
    return [
        {
            "session_id": 10,
            "at": datetime(2026, 8, 24, 21, tzinfo=KST),
            "sender": "a",
            "snippet": "오늘 하루는 어땠어",
            "score": 0.9,
        }
    ]


def test_interpret_agent_is_korean_grounded_plural_and_number_free():
    async def scenario():
        knowledge = Knowledge(
            docs={
                ("question_rate", "down"): [
                    {
                        "doc": "communication.md",
                        "section": "관심 표현",
                        "text": "질문은 관심 표현이 될 수 있다",
                        "source": "source-a",
                    }
                ]
            }
        )
        agent = InterpretAgent(
            _MockAI(),
            _conversation_tool,
            partial(search_knowledge, knowledge=knowledge),
        )
        trace = []
        output = await agent.run(
            {
                "couple_id": uuid4(),
                "metric": "question_rate",
                "direction": "down",
                "magnitude": "slight",
            },
            trace=trace,
        )
        highlight = output.highlights[0]
        assert len(highlight.interpretations) >= 2
        assert all(not item.endswith(".") for item in highlight.interpretations)
        assert all("때문에" not in item for item in highlight.interpretations)
        assert re.search(r"[가-힣]", highlight.observation)
        assert not re.search(r"\d", " ".join([highlight.observation, *highlight.interpretations]))
        assert not re.search(r"\b[AB](?:가|이|는|은)|상대방|누가 더", " ".join([highlight.observation, *highlight.interpretations]))
        patterns_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "banned_patterns.txt"
        patterns = [
            re.compile(line.strip())
            for line in patterns_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert not any(
            pattern.search(text)
            for pattern in patterns
            for text in [highlight.observation, *highlight.interpretations]
        )
        assert {(item.session_id, item.snippet) for item in highlight.evidence} <= {
            (10, "오늘 하루는 어땠어")
        }
        assert {(item.doc, item.section) for item in highlight.sources} <= {
            ("communication.md", "관심 표현")
        }
        assert trace[0]["agent"] == "interpret"

        empty_agent = InterpretAgent(_MockAI(), lambda *_args: [], lambda *_args: [])
        empty = await empty_agent.run(
            {
                "couple_id": uuid4(),
                "metric": "question_rate",
                "direction": "up",
                "magnitude": "clear",
            }
        )
        assert empty.highlights[0].evidence == []
        assert empty.highlights[0].sources == []

    asyncio.run(scenario())


def test_invalid_agent_schema_retries_only_once():
    async def scenario():
        ai = _InvalidAI()
        agent = InterpretAgent(ai, lambda *_args: [], lambda *_args: [])
        with pytest.raises(AgentOutputError):
            await agent.run(
                {
                    "couple_id": uuid4(),
                    "metric": "question_rate",
                    "direction": "down",
                    "magnitude": "slight",
                }
            )
        assert ai.calls == 2

    asyncio.run(scenario())


def test_suggest_agent_uses_only_templates_and_one_sentence():
    async def scenario():
        knowledge = Knowledge(
            templates={
                ("question_rate", "down"): [
                    {
                        "template_id": "q_down_02",
                        "text": "서로의 하루에서 궁금한 점을 하나 나눠보면 어떨까요.",
                    },
                    {
                        "template_id": "q_down_01",
                        "text": "최근 기억에 남은 일을 차분히 물어볼 수 있어요.",
                    },
                    {
                        "template_id": "bad",
                        "text": "더 자주 연락하세요.",
                    },
                ]
            }
        )
        templates = partial(get_suggestion_templates, knowledge=knowledge)
        agent = SuggestAgent(_MockAI(), templates)
        output = await agent.run(
            {
                "metric": "question_rate",
                "direction": "down",
                "magnitude": "slight",
                "linked_highlight": "h1",
            }
        )
        tool_rows = templates("question_rate", "down")
        by_id = {item["template_id"]: item["text"] for item in tool_rows}
        assert 1 <= len(output.suggestions) <= 2
        assert all(item.template_id in by_id for item in output.suggestions)
        assert all(item.text == by_id[item.template_id] for item in output.suggestions)
        assert all("하세요" not in item.text and "해야" not in item.text for item in output.suggestions)
        assert all(not re.search(r"[.!?。].+[.!?。]", item.text) for item in output.suggestions)

    asyncio.run(scenario())


def test_resume_delay_outlier_uses_real_canonical_template():
    async def scenario():
        knowledge = load_knowledge(KNOWLEDGE_ROOT)
        signal = _outlier_signals(
            [{"metric": "resume_delay", "direction": "high"}]
        )[0]
        assert signal["metric"] == "resume_delay_median_min"
        assert signal["direction"] == "up"

        tool = partial(get_suggestion_templates, knowledge=knowledge)
        rows = tool(signal["metric"], signal["direction"])
        assert rows
        output = await SuggestAgent(_MockAI(), tool).run(
            {
                "metric": signal["metric"],
                "direction": signal["direction"],
                "magnitude": "clear",
                "linked_highlight": "h1",
            }
        )
        by_id = {row["template_id"]: row["text"] for row in rows}
        assert 1 <= len(output.suggestions) <= 2
        assert all(item.template_id in by_id for item in output.suggestions)
        assert all(item.text == by_id[item.template_id] for item in output.suggestions)

    asyncio.run(scenario())


def test_real_knowledge_templates_cover_every_selectable_metric_direction():
    async def scenario():
        knowledge = load_knowledge(KNOWLEDGE_ROOT)
        assert knowledge.templates
        template_ids = [
            row["template_id"]
            for rows in knowledge.templates.values()
            for row in rows
        ]
        assert len(template_ids) == len(set(template_ids))

        tool = partial(get_suggestion_templates, knowledge=knowledge)
        agent = SuggestAgent(_MockAI(), tool)
        for metric in SELECTABLE_AGENT_METRICS:
            for direction in ("up", "down"):
                rows = tool(metric, direction)
                assert rows, f"missing template: {metric}/{direction}"
                output = await agent.run(
                    {
                        "metric": metric,
                        "direction": direction,
                        "magnitude": "clear",
                        "linked_highlight": "h1",
                    }
                )
                allowed = {row["template_id"]: row["text"] for row in rows}
                assert 1 <= len(output.suggestions) <= 2
                assert all(item.template_id in allowed for item in output.suggestions)
                assert all(item.text == allowed[item.template_id] for item in output.suggestions)
                assert all(
                    "하세요" not in item.text and "해야" not in item.text
                    for item in output.suggestions
                )
                assert all(_one_sentence_for_test(item.text) for item in output.suggestions)

    asyncio.run(scenario())


def _one_sentence_for_test(text: str) -> bool:
    inner = text.strip().rstrip(".!?。")
    return bool(inner) and not re.search(r"[.!?。]", inner)


def test_unknown_real_template_combination_fails_clearly():
    knowledge = load_knowledge(KNOWLEDGE_ROOT)
    agent = SuggestAgent(
        _MockAI(),
        partial(get_suggestion_templates, knowledge=knowledge),
    )
    with pytest.raises(AgentOutputError, match="사용 가능한 제안 템플릿"):
        asyncio.run(
            agent.run(
                {
                    "metric": "unknown_metric",
                    "direction": "up",
                    "magnitude": "clear",
                    "linked_highlight": "h1",
                }
            )
        )

def test_suggest_agent_does_not_invent_when_templates_are_empty():
    async def scenario():
        agent = SuggestAgent(_MockAI(), lambda *_args: [])
        with pytest.raises(AgentOutputError):
            await agent.run(
                {
                    "metric": "question_rate",
                    "direction": "down",
                    "magnitude": "slight",
                    "linked_highlight": "h1",
                }
            )

    asyncio.run(scenario())


def test_safety_agent_rewrites_required_cases_and_ignores_moments():
    async def scenario():
        agent = SafetyAgent(_MockAI())
        banned = [
            "관계 온도 72점이에요",
            "B가 무심해진 것 같아요",
            "더 자주 연락하세요",
            "질문이 30% 줄었어요",
            "A가 묻는 질문이 줄었어요",
        ]
        result = await agent.run({"interpretations": banned})
        assert result.passed is False
        assert {item.before for item in result.rewritten} == set(banned)
        assert all(
            not item.after or not agent._is_banned(item.after)
            for item in result.rewritten
        )

        full_shape = await agent.run(
            {
                "highlights": [
                    {
                        "id": "h1",
                        "metric": "question_rate",
                        "observation": "질문이 30% 줄었어요",
                        "interpretations": ["바쁜 시기였을 수도", "리듬이 바뀐 걸 수도"],
                        "evidence": [],
                        "sources": [],
                        "sentiment": "neutral",
                    }
                ],
                "suggestions": [
                    {
                        "id": "s1",
                        "linked_highlight": "h1",
                        "template_id": "t1",
                        "text": "더 자주 연락하세요",
                    }
                ],
            }
        )
        assert full_shape.passed is False

        allowed = await agent.run(
            {"observation": "지난 4주에 비해 묻는 순간이 좀 줄어들었어요"}
        )
        assert allowed.passed is True and allowed.rewritten == []

        moment_only = await agent.run(
            {"moments": [{"text": "A가 질문을 30% 덜 한 순간"}]}
        )
        assert moment_only.passed is True and moment_only.rewritten == []

    asyncio.run(scenario())


# ---------------------------------------------------------------- 챗봇 (TASKS 3-6)


CHAT_INTENT_CASES = [
    ("우리 언제 처음 자기야라고 불렀지?", "fact_query"),
    ("그때 제주도 얘기 언제 했었지?", "fact_query"),
    ("요즘 우리 질문 많이 해?", "metric_query"),
    ("답장 빨라졌어?", "metric_query"),
    ("지난주 리포트 요약해줘", "report_query"),
    ("오늘 날씨 어때?", "other"),
]


@pytest.mark.parametrize("message,expected", CHAT_INTENT_CASES)
def test_chat_intent_agent_mock_classifies_by_keyword_hint(message, expected):
    async def scenario():
        agent = ChatIntentAgent(_MockAI())
        output = await agent.run({"message": message, "focus_range": None, "history": []})
        assert output.intent == expected

    asyncio.run(scenario())


def test_chat_answer_agent_fact_query_grounds_citations_in_candidates():
    async def scenario():
        candidates = _conversation_tool(uuid4(), "자기야")
        agent = ChatAnswerAgent(_MockAI())
        output = await agent.run(
            "fact_query",
            {
                "message": "자기야라고 언제 불렀지?",
                "focus_range": None,
                "history": [],
                "evidence_candidates": candidates,
            },
            candidates=candidates,
        )
        assert output.citations
        cited = output.citations[0]
        assert (cited.session_id, cited.snippet) == (10, "오늘 하루는 어땠어")

    asyncio.run(scenario())


def test_chat_answer_agent_fact_query_without_candidates_is_no_record():
    async def scenario():
        agent = ChatAnswerAgent(_MockAI())
        output = await agent.run(
            "fact_query",
            {
                "message": "존재하지 않는 얘기 언제 했지?",
                "focus_range": None,
                "history": [],
                "evidence_candidates": [],
            },
            candidates=[],
        )
        assert output.answer == NO_RECORD_TEXT
        assert output.citations == []

    asyncio.run(scenario())


def test_chat_answer_agent_metric_query_reuses_tool_comment_without_new_numbers():
    async def scenario():
        agent = ChatAnswerAgent(_MockAI())
        metrics = {
            "range": {"question_rate": {"couple": 0.2, "mine": 0.1}},
            "baseline": {"question_rate": {"couple": 0.23, "mine": 0.22}},
            "comment": "지난 8주보다 답장이 많이 느려졌어요",
        }
        output = await agent.run(
            "metric_query",
            {"message": "요즘 답장 느려졌어?", "focus_range": None, "history": [], "metrics": metrics},
        )
        # mock 모드는 LLM을 호출하지 않으므로 comment를 그대로 재사용한다 — "재계산 없이 그대로
        # 옮긴다"는 계약을 코드가 지키는지 확인 (숫자 유무 자체는 이 테스트의 관심사가 아니다:
        # baseline 기간("8주")처럼 정당한 숫자가 comment 안에 이미 있을 수 있다).
        assert output.answer == metrics["comment"]
        assert output.citations == []

    asyncio.run(scenario())


def test_chat_answer_agent_report_query_pending_is_honest_not_invented():
    async def scenario():
        agent = ChatAnswerAgent(_MockAI())
        output = await agent.run(
            "report_query",
            {"message": "이번주 리포트 뭐래?", "focus_range": None, "history": [], "report": None},
        )
        assert "준비되지" in output.answer
        assert output.citations == []

    asyncio.run(scenario())
