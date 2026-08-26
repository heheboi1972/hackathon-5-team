"""리포트 에이전트 사이에서만 사용하는 엄격한 Pydantic 계약."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

Direction = Literal["up", "down"]
Magnitude = Literal["slight", "clear"]
Valence = Literal["positive", "negative", "neutral"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MetricSignal(StrictModel):
    metric: str = Field(min_length=1)
    direction: Literal["up", "down", "steady"]
    magnitude: Magnitude = "slight"
    comparable: bool = True
    outlier_ref: str | None = Field(
        default=None, validation_alias=AliasChoices("outlier_ref", "ref")
    )
    valence: Valence | None = Field(
        default=None,
        validation_alias=AliasChoices("valence", "sentiment", "polarity"),
    )


class SelectInput(StrictModel):
    metrics: list[MetricSignal] = Field(default_factory=list)
    outliers: list[MetricSignal] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class SelectedCandidate(StrictModel):
    metric: str = Field(min_length=1)
    direction: Direction
    outlier_ref: str | None = None
    reason: str = Field(min_length=1)


class SelectOutput(StrictModel):
    candidates: list[SelectedCandidate] = Field(default_factory=list, max_length=3)


class InterpretInput(StrictModel):
    couple_id: UUID | str
    metric: str = Field(min_length=1)
    direction: Direction
    magnitude: Magnitude
    outlier_ref: str | None = None
    query: str | None = None
    start: datetime | None = None
    end: datetime | None = None


class EvidenceCandidate(StrictModel):
    session_id: int
    at: datetime
    sender: Literal["a", "b"] | None = None
    snippet: str
    score: float | None = None


class KnowledgeCandidate(StrictModel):
    doc: str
    section: str = ""
    text: str = ""
    source: str | None = None


class AgentEvidence(StrictModel):
    session_id: int
    at: datetime
    snippet: str


class AgentSource(StrictModel):
    doc: str
    section: str = ""


class InterpretedHighlight(StrictModel):
    observation: str = Field(min_length=1)
    interpretations: list[str] = Field(min_length=2)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    sources: list[AgentSource] = Field(default_factory=list)

    @field_validator("interpretations")
    @classmethod
    def interpretations_are_clauses(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            item = value.strip()
            if not item or item.endswith((".", "!", "?", "。")):
                raise ValueError("interpretation은 마침표 없는 절이어야 합니다")
            if item.endswith(("요", "다", "니다", "예요", "이에요")):
                raise ValueError("interpretation은 종결어미 없는 절이어야 합니다")
            if len(item) > 40:
                raise ValueError("interpretation은 40자 이하여야 합니다 (ISSUE C9)")
            cleaned.append(item)
        return cleaned


class InterpretOutput(StrictModel):
    highlights: list[InterpretedHighlight] = Field(min_length=1)


class SuggestInput(StrictModel):
    metric: str = Field(min_length=1)
    direction: Direction
    magnitude: Magnitude
    linked_highlight: str = Field(min_length=1)


class SuggestionTemplate(StrictModel):
    template_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class AgentSuggestion(StrictModel):
    linked_highlight: str
    template_id: str
    text: str = Field(min_length=1)


class SuggestOutput(StrictModel):
    suggestions: list[AgentSuggestion] = Field(min_length=1, max_length=2)


class SafetyHighlightInput(StrictModel):
    id: str | None = None
    metric: str | None = None
    observation: str | None = None
    interpretations: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    sentiment: str | None = None


class SafetySuggestionInput(StrictModel):
    id: str | None = None
    linked_highlight: str | None = None
    template_id: str | None = None
    text: str


class SafetyInput(StrictModel):
    observation: str | None = None
    interpretations: list[str] = Field(default_factory=list)
    highlights: list[SafetyHighlightInput] = Field(default_factory=list)
    suggestions: list[SafetySuggestionInput] = Field(default_factory=list)
    moments: list[dict[str, Any]] = Field(default_factory=list)


class Rewrite(StrictModel):
    before: str
    after: str


class SafetyOutput(StrictModel):
    passed: bool
    rewritten: list[Rewrite] = Field(default_factory=list)


class AgentTraceStep(StrictModel):
    agent: Literal["select", "interpret", "suggest", "safety"]
    input: dict[str, Any]
    output: dict[str, Any]


# ---------------------------------------------------------------- 챗봇 (TASKS 3-6, FR-006)
# term_count/advice_request는 chat_supervisor가 정규식으로 먼저 걸러 LLM을 거치지 않는다
# (prompts/chat_intent.md·chat_answer.md 참고) — 여기 모델 2개는 그 나머지(intent 분류/답변 생성)만 다룬다.

ChatIntent = Literal["fact_query", "metric_query", "report_query", "advice_request", "other"]


class ChatIntentOutput(StrictModel):
    intent: ChatIntent


class ChatCitation(StrictModel):
    """report 쪽 AgentEvidence와 달리 sender를 남긴다 — 이미 두 사람이 나눈 대화의 사실
    정보라 P-3(비교 금지) 대상이 아니다(chat_answer.md 규칙 참고)."""
    session_id: int
    at: datetime
    sender: Literal["a", "b"]
    snippet: str


class ChatAnswerOutput(StrictModel):
    answer: str = Field(min_length=1)
    citations: list[ChatCitation] = Field(default_factory=list)
    # LLM이 입력으로 받은 metrics(range/baseline/comment)를 그대로 echo하지만, 코드는 이 값을
    # 쓰지 않는다 — chat_supervisor가 툴이 준 원본을 ChatResponse.metrics에 직접 붙인다
    # (숫자는 코드가 만든다, P-2 — LLM의 "그대로 옮기기"를 신뢰하지 않고 구조적으로 강제).
    metrics: dict[str, Any] | None = None
