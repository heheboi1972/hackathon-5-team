"""에이전트 2: tool 근거 안에서만 관찰과 복수 해석 가능성을 만든다."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from ..models.report import (
    AgentEvidence,
    AgentSource,
    EvidenceCandidate,
    InterpretInput,
    InterpretedHighlight,
    InterpretOutput,
    KnowledgeCandidate,
)
from ..services.ai_service import AIService
from .base import AgentBase, AgentOutputError, maybe_await

Tool = Callable[..., Any]

# watsonx json_schema 구조화 출력 (2-6b 실측 10/10, 2026-08-25 윤아 — 3-7).
# evidence/sources가 프롬프트 지시만으로는 가끔 문자열로 축약되던 문제를 API 레벨에서 막는다.
# scripts/2-6b_response_format_test.py 와 동일한 스키마 — InterpretOutput 실제 필드와 1:1.
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "interpret_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "highlights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "observation": {"type": "string"},
                            "interpretations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                            },
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "session_id": {"type": "integer"},
                                        "at": {"type": "string"},
                                        "snippet": {"type": "string"},
                                    },
                                    "required": ["session_id", "at", "snippet"],
                                    "additionalProperties": False,
                                },
                            },
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "doc": {"type": "string"},
                                        "section": {"type": "string"},
                                    },
                                    "required": ["doc", "section"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["observation", "interpretations", "evidence", "sources"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["highlights"],
            "additionalProperties": False,
        },
    },
}
_KOREAN_RE = re.compile(r"[가-힣]")
_DIGIT_RE = re.compile(r"\d")
_PERSON_RE = re.compile(r"(?:\b[AB]\s*(?:가|이|는|은|의|님|씨)\b|상대방|파트너|누가\s*더|한\s*쪽)")
_BANNED_PATTERNS = [
    re.compile(line.strip())
    for line in (
        Path(__file__).resolve().parents[1] / "prompts" / "banned_patterns.txt"
    ).read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
]

_LABELS = {
    "question_rate": "서로에게 묻는 순간",
    "message_length_median": "한 번에 나누는 이야기의 길이",
    "reply_gap_median_min": "대화가 이어지는 간격",
    "resume_delay_median_min": "대화를 다시 잇는 간격",
    "session_length_median": "한 번에 이어지는 대화의 길이",
}

_INTERPRETATIONS = {
    "question_rate": [
        "바쁜 시기였을 수도",
        "대화 주제가 일상 공유 쪽으로 옮겨간 걸 수도",
    ],
    "message_length_median": [
        "짧게 안부를 주고받는 날이 많았을 수도",
        "한 번에 전하는 이야기의 방식이 달라진 걸 수도",
    ],
    "reply_gap_median_min": [
        "각자의 일정이 바빴을 수도",
        "대화를 이어가는 시간대가 달라졌을 수도",
    ],
    "resume_delay_median_min": [
        "대화를 다시 시작할 여유가 달라졌을 수도",
        "일상 리듬이 잠시 바뀐 걸 수도",
    ],
}


def _mock_output(
    model: InterpretInput,
    evidence: list[EvidenceCandidate],
    knowledge: list[KnowledgeCandidate],
) -> InterpretOutput:
    label = _LABELS.get(model.metric, "대화의 흐름")
    degree = "눈에 띄게" if model.magnitude == "clear" else "조금"
    change = "늘어났어요" if model.direction == "up" else "줄어들었어요"
    clauses = _INTERPRETATIONS.get(
        model.metric,
        ["일상의 리듬이 달라졌을 수도", "대화 주제가 옮겨간 걸 수도"],
    )
    return InterpretOutput(
        highlights=[
            InterpretedHighlight(
                observation=f"지난 흐름에 비해 {label}이 {degree} {change}",
                interpretations=clauses,
                evidence=[
                    AgentEvidence(
                        session_id=item.session_id, at=item.at, snippet=item.snippet
                    )
                    for item in evidence[:2]
                ],
                sources=[
                    AgentSource(doc=item.doc, section=item.section)
                    for item in knowledge[:2]
                ],
            )
        ]
    )


def _validate_language(output: InterpretOutput) -> None:
    for highlight in output.highlights:
        texts = [highlight.observation, *highlight.interpretations]
        for text in texts:
            if not _KOREAN_RE.search(text):
                raise AgentOutputError("interpret 출력은 한국어여야 합니다")
            if _DIGIT_RE.search(text):
                raise AgentOutputError("observation/interpretations에 숫자를 쓸 수 없습니다")
            if (
                "때문에" in text
                or _PERSON_RE.search(text)
                or any(pattern.search(text) for pattern in _BANNED_PATTERNS)
            ):
                raise AgentOutputError("banned_patterns 금지 표현이 있습니다")


def _validate_grounding(
    output: InterpretOutput,
    evidence: list[EvidenceCandidate],
    knowledge: list[KnowledgeCandidate],
) -> None:
    evidence_keys = {
        (item.session_id, item.at, item.snippet) for item in evidence
    }
    source_keys = {(item.doc, item.section) for item in knowledge}
    for highlight in output.highlights:
        if any(
            (item.session_id, item.at, item.snippet) not in evidence_keys
            for item in highlight.evidence
        ):
            raise AgentOutputError("search_conversation 밖의 evidence가 있습니다")
        if any(
            (item.doc, item.section) not in source_keys for item in highlight.sources
        ):
            raise AgentOutputError("search_knowledge 밖의 source가 있습니다")


class InterpretAgent(AgentBase):
    def __init__(
        self,
        ai: AIService,
        search_conversation: Tool,
        search_knowledge: Tool,
    ):
        super().__init__("interpret", ai, "interpret.md")
        self.search_conversation = search_conversation
        self.search_knowledge = search_knowledge

    async def run(
        self,
        payload: InterpretInput | dict[str, Any],
        *,
        trace: list[dict[str, Any]] | None = None,
    ) -> InterpretOutput:
        model = payload if isinstance(payload, InterpretInput) else InterpretInput.model_validate(payload)
        query = model.query or f"{model.metric} {model.direction} 대화 흐름"
        with self.span() as span:
            raw_evidence = await maybe_await(
                self.search_conversation(
                    model.couple_id, query, model.start, model.end, 8
                )
            )
            raw_knowledge = await maybe_await(
                self.search_knowledge(model.metric, model.direction, 5)
            )
            evidence = [EvidenceCandidate.model_validate(item) for item in (raw_evidence or [])]
            knowledge = [KnowledgeCandidate.model_validate(item) for item in (raw_knowledge or [])]
            tool_payload = {
                **model.model_dump(mode="json"),
                "evidence_candidates": [item.model_dump(mode="json") for item in evidence],
                "knowledge": [item.model_dump(mode="json") for item in knowledge],
            }
            if self.ai.provider_name == "mock":
                output = _mock_output(model, evidence, knowledge)
            else:
                output = await self.generate_validated(
                    tool_payload,
                    InterpretOutput,
                    mock_key="interpret",
                    response_format=_RESPONSE_FORMAT,
                )
            _validate_language(output)
            _validate_grounding(output, evidence, knowledge)
            span.set_attribute("evidence_count", len(evidence))
            span.set_attribute("source_count", len(knowledge))
        self.record_trace(trace, self.name, tool_payload, output)
        return output
