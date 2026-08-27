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
from app.agents.chat_answer_agent import ADVICE_FALLBACK_TEXT, ChatAnswerAgent, NO_RECORD_TEXT
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

        duplicate_outliers = await agent.run(
            {
                "outliers": [
                    {
                        "metric": "reply_gap_median_min",
                        "direction": "up",
                        "magnitude": "clear",
                        "outlier_ref": f"outlier:{index}",
                    }
                    for index in range(3)
                ]
                + [
                    {
                        "metric": "resume_delay_median_min",
                        "direction": "up",
                        "magnitude": "clear",
                        "outlier_ref": "outlier:3",
                    }
                ]
            }
        )
        assert [item.metric for item in duplicate_outliers.candidates] == [
            "reply_gap_median_min",
            "resume_delay_median_min",
        ]

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

        empty_agent = InterpretAgent(_MockAI(), lambda *_args, **_kwargs: [], lambda *_args, **_kwargs: [])
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
        agent = InterpretAgent(ai, lambda *_args, **_kwargs: [], lambda *_args, **_kwargs: [])
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


def test_interpret_agent_recovers_banned_expression_without_failing_report():
    class CorrectingAI:
        provider_name = "watsonx"

        def __init__(self, corrected: bool):
            self.calls = 0
            self.corrected = corrected

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1 or not self.corrected:
                observation = "A가 질문을 더 적게 했어요"
                interpretations = ["바쁜 일정 때문일 수도", "상대방에게 물어볼 것이 적었을 수도"]
            else:
                observation = "우리 대화에서 묻는 순간이 조금 줄었어요"
                interpretations = ["바쁜 시기였을 수도", "일상 공유가 자연스럽게 이어졌을 수도"]
            return {
                "highlights": [{
                    "observation": observation,
                    "interpretations": interpretations,
                    "evidence": [],
                    "sources": [],
                }]
            }

    async def scenario():
        payload = {
            "couple_id": uuid4(),
            "metric": "question_rate",
            "direction": "down",
            "magnitude": "slight",
        }

        corrected_ai = CorrectingAI(corrected=True)
        corrected = await InterpretAgent(
            corrected_ai, lambda *_args, **_kwargs: [], lambda *_args, **_kwargs: []
        ).run(payload)
        assert corrected_ai.calls == 2
        assert corrected.highlights[0].observation == "우리 대화에서 묻는 순간이 조금 줄었어요"

        fallback_ai = CorrectingAI(corrected=False)
        fallback = await InterpretAgent(
            fallback_ai, lambda *_args, **_kwargs: [], lambda *_args, **_kwargs: []
        ).run(payload)
        assert fallback_ai.calls == 2
        texts = [fallback.highlights[0].observation, *fallback.highlights[0].interpretations]
        patterns_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "banned_patterns.txt"
        patterns = [
            re.compile(line.strip())
            for line in patterns_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        assert not any(pattern.search(text) for pattern in patterns for text in texts)
        assert all("A가" not in text and "상대방" not in text and "때문" not in text for text in texts)

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
        agent = SuggestAgent(_MockAI(), lambda *_args, **_kwargs: [])
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


# ------------------------------------ advice_request (2026-08-27, 고정 문구 → LLM 생성 전환)


class _ScriptedAI:
    """generate_json이 항상 미리 정해둔 dict를 돌려주는 가짜 실 LLM (provider_name != mock이라
    ChatAnswerAgent.run()이 실제 LLM 분기를 타게 만든다)."""

    provider_name = "watsonx"

    def __init__(self, response: dict):
        self.response = response

    async def generate_json(self, *_args, **_kwargs):
        return self.response


def test_chat_answer_agent_advice_request_mock_uses_fallback_text():
    """mock provider에서는 LLM을 안 부르므로 항상 고정 폴백 문구를 그대로 쓴다."""
    async def scenario():
        agent = ChatAnswerAgent(_MockAI())
        output = await agent.run(
            "advice_request", {"message": "앞으로 어떻게 해야 할까?", "history": []}
        )
        assert output.answer == ADVICE_FALLBACK_TEXT
        assert output.citations == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "우리 어떻게 화해해야 할까?",
            '화해 방법을 직접 정해드리지는 않지만, 최근 갈등이 시작된 대화나 두 분의 대화 흐름을 함께 확인할 수 있어요. '
            '"최근에 분위기가 달라진 시점을 알려줘"라고 물어보시면 관련 기록을 찾아드릴게요.',
        ),
        (
            "이 정도면 헤어지는 게 나을까?",
            '관계를 계속할지는 판단해드리지 않아요. 대신 최근 대화량, 답장 시간, 질문 비율 등 대화 패턴이 어떻게 변했는지 확인할 수 있어요. '
            '"최근 우리 대화 패턴이 어떻게 변했는지"라고 물어보시면 관련 지표를 보여드릴게요.',
        ),
        (
            "요즘 연락이 좀 뜸한데 어떻게 하면 좋을까?",
            '연락이 줄었다고 느끼셨군요. 이 챗봇은 직접적인 조언을 드리지 않지만, 최근 연락 빈도와 답장 시간이 어떻게 변했는지 확인해드릴 수 있어요. '
            '"최근 연락이 얼마나 줄었는지"라고 물어보시면 관련 지표를 보여드릴게요.',
        ),
        (
            "서로 서운한 게 쌓이지 않으려면 어떻게 해야 할까?",
            '서운함이 쌓이는 상황을 직접 해결해드리지는 않지만, 최근 대화에서 서운함이 언급된 시점과 그 전후 흐름을 확인할 수 있어요. '
            '"서운함이 처음 나타난 대화를 알려줘"라고 물어보시면 관련 기록을 찾아드릴게요.',
        ),
        (
            "여자친구가 삐지면 어떻게 해야 돼?",
            '여자친구가 삐졌다고 느끼셨군요. 이 챗봇은 관계에 대한 판단이나 조언을 제공하지 않아요. '
            '대신 최근 대화에서 감정이 변한 시점이나 대화 패턴을 확인할 수 있어요. '
            '"최근에 감정이 바뀐 대화가 언제였는지 알려줘"라고 물어보시면 관련 기록을 찾아드릴게요.',
        ),
        (
            "우리 궁합 잘 맞는 편이야?",
            '두 분의 관계를 평가하거나 점수로 판단하지는 않아요. 대신 최근 대화량, 질문 비율, 답장 시간 등 대화 패턴 변화를 확인할 수 있어요. '
            '"최근 우리 대화 패턴이 어떻게 변했는지"라고 물어보시면 관련 지표를 보여드릴게요.',
        ),
        (
            "화해하려면 뭐부터 해야 돼?",
            '화해 방법을 직접 정해드리지는 않지만, 최근 갈등이 시작된 대화나 두 분의 대화 흐름을 함께 확인할 수 있어요. '
            '"최근에 분위기가 달라진 시점을 알려줘"라고 물어보시면 관련 기록을 찾아드릴게요.',
        ),
        (
            "이 정도면 그만 만나는 게 맞는 걸까?",
            '그 상황에 대해 고민하고 계시군요. 이 챗봇은 관계를 평가하거나 판단해드리지 않아요. '
            '대신 최근 대화량, 답장 시간, 질문 비율 등 대화 패턴 변화를 확인할 수 있어요. '
            '"최근 우리 대화 패턴이 어떻게 변했는지"라고 물어보시면 관련 기록을 보여드릴게요.',
        ),
    ],
)
def test_chat_answer_agent_advice_request_uses_canonical_answers(message, expected):
    async def scenario():
        agent = ChatAnswerAgent(_MockAI())
        output = await agent.run("advice_request", {"message": message, "history": []})
        assert output.answer == expected
        assert output.citations == []

    asyncio.run(scenario())


def test_chat_answer_agent_advice_request_uses_llm_text_when_safe():
    """banned_patterns.txt에 안 걸리는 안전한 문장이면 LLM이 만든 문장을 그대로 쓴다 —
    고정 문구로 덮어쓰지 않는다(이번 전환의 핵심: 더 이상 항상 같은 문장이 아니어야 함)."""
    async def scenario():
        ai = _ScriptedAI(
            {
                "answer": "요즘 연락이 뜸해서 신경 쓰이시는군요. 이 챗봇은 관계를 판단하지 않지만, "
                "대신 요즘 대화가 어땠는지는 같이 볼 수 있어요.",
                "citations": [],
            }
        )
        agent = ChatAnswerAgent(ai)
        output = await agent.run(
            "advice_request", {"message": "요즘 마음이 복잡한데 어떡하지", "history": []}
        )
        assert output.answer != ADVICE_FALLBACK_TEXT
        assert "신경 쓰이시는군요" in output.answer
        assert output.citations == []

    asyncio.run(scenario())


def test_chat_answer_agent_advice_request_falls_back_when_llm_gives_advice():
    """LLM이 규칙을 어기고 실제 조언("먼저 연락해보세요")을 만들면, banned_patterns.txt에
    걸려서 무조건 고정 폴백 문구로 되돌아간다 — 이 서비스의 핵심 안전 원칙이라 LLM 혼자
    믿지 않는다는 걸 확인하는 테스트."""
    async def scenario():
        ai = _ScriptedAI(
            {"answer": "먼저 연락해보세요, 그러면 관계가 다시 편해질 거예요.", "citations": []}
        )
        agent = ChatAnswerAgent(ai)
        output = await agent.run(
            "advice_request", {"message": "어떻게 해야 할까", "history": []}
        )
        assert output.answer == ADVICE_FALLBACK_TEXT

    asyncio.run(scenario())


def test_chat_answer_agent_advice_request_forces_citations_empty():
    """advice_request는 대화 인용 대상이 아니므로, LLM이 실수로 citations를 채워도 서버가
    강제로 비운다."""
    async def scenario():
        ai = _ScriptedAI(
            {
                "answer": "요즘 연락이 뜸해서 신경 쓰이시는군요. 대화 기록은 같이 볼 수 있어요.",
                "citations": [
                    {"session_id": 1, "at": "2026-08-20T10:00:00+09:00", "sender": "a", "snippet": "안녕"}
                ],
            }
        )
        agent = ChatAnswerAgent(ai)
        output = await agent.run(
            "advice_request", {"message": "요즘 연락 뜸한데 어떡하지", "history": []}
        )
        assert output.citations == []

    asyncio.run(scenario())
