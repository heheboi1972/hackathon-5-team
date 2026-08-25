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
from app.agents.interpret_agent import InterpretAgent
from app.agents.safety_agent import SafetyAgent
from app.agents.select_agent import SelectAgent
from app.agents.suggest_agent import SuggestAgent
from app.models.report import SelectOutput
from app.services.knowledge import Knowledge
from app.tools.get_suggestion_templates import get_suggestion_templates
from app.tools.search_knowledge import search_knowledge

KST = ZoneInfo("Asia/Seoul")


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
