"""에이전트 4: LLM 문장만 regex로 찾고 안전하게 재작성하거나 제거한다."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models.report import Rewrite, SafetyInput, SafetyOutput
from ..services.ai_service import AIService
from .base import AgentBase, AgentOutputError

# watsonx json_schema 구조화 출력 (2026-08-25 윤아 — 3-7, interpret_agent.py와 같은 이유).
# SafetyOutput 실제 필드(passed: bool, rewritten: [{before, after}])와 1:1.
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "safety_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "rewritten": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "before": {"type": "string"},
                            "after": {"type": "string"},
                        },
                        "required": ["before", "after"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["passed", "rewritten"],
            "additionalProperties": False,
        },
    },
}


def load_banned_patterns(path: Path | None = None) -> list[re.Pattern[str]]:
    target = path or (
        Path(__file__).resolve().parents[1] / "prompts" / "banned_patterns.txt"
    )
    return [
        re.compile(line.strip())
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _targets(model: SafetyInput) -> list[str]:
    texts: list[str] = []
    if model.observation:
        texts.append(model.observation)
    texts.extend(model.interpretations)
    for highlight in model.highlights:
        if highlight.observation:
            texts.append(highlight.observation)
        texts.extend(highlight.interpretations)
    texts.extend(item.text for item in model.suggestions)
    # moments는 의도적으로 포함하지 않는다.
    return texts


def _rewrite(text: str) -> str:
    if "관계 온도" in text or re.search(r"[ABCDF]\s*등급", text):
        return ""
    if re.search(r"\bB\s*(?:가|이|는|은)", text) and "무심" in text:
        return "요즘 대화의 분위기가 조금 달라 보였어요"
    if "더 자주 연락하세요" in text:
        return "서로 편한 때에 연락을 이어가 보면 어떨까요"
    if re.search(r"질문이\s*\d+\s*(?:%|퍼센트)", text):
        return "묻는 순간이 좀 줄어들었어요"
    if re.search(r"\bA\s*(?:가|이|는|은).*질문", text):
        return "서로에게 묻는 순간이 좀 줄어들었어요"
    rewritten = re.sub(
        r"\b[AB]\s*(?:가|이|는|은|의|님|씨)\b", "우리", text
    )
    rewritten = re.sub(r"\d+\s*(?:%|퍼센트|배|점|등급)", "조금", rewritten)
    rewritten = rewritten.replace("하세요", "해보면 어떨까요")
    rewritten = rewritten.replace("해보세요", "해보면 어떨까요")
    rewritten = re.sub(r"해야\s*(?:해|합니다|해요)", "해볼 수 있어요", rewritten)
    rewritten = rewritten.replace("때문에", "일 수도 있어")
    return rewritten.strip()


class SafetyAgent(AgentBase):
    def __init__(self, ai: AIService, patterns_path: Path | None = None):
        super().__init__("safety", ai, "safety.md")
        self.patterns = load_banned_patterns(patterns_path)

    def _is_banned(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.patterns)

    async def run(
        self,
        payload: SafetyInput | dict[str, Any],
        *,
        trace: list[dict[str, Any]] | None = None,
    ) -> SafetyOutput:
        model = payload if isinstance(payload, SafetyInput) else SafetyInput.model_validate(payload)
        with self.span() as span:
            flagged = list(dict.fromkeys(text for text in _targets(model) if self._is_banned(text)))
            if not flagged:
                output = SafetyOutput(passed=True, rewritten=[])
            elif self.ai.provider_name == "mock":
                output = SafetyOutput(
                    passed=False,
                    rewritten=[Rewrite(before=text, after=_rewrite(text)) for text in flagged],
                )
            else:
                generated = await self.generate_validated(
                    {"sentences": flagged},
                    SafetyOutput,
                    mock_key="safety",
                    response_format=_RESPONSE_FORMAT,
                )
                by_before = {
                    item.before: item.after
                    for item in generated.rewritten
                    if item.before in flagged
                }
                output = SafetyOutput(
                    passed=False,
                    rewritten=[
                        Rewrite(before=text, after=by_before.get(text, ""))
                        for text in flagged
                    ],
                )
            cleaned = []
            for item in output.rewritten:
                after = item.after if not self._is_banned(item.after) else ""
                cleaned.append(Rewrite(before=item.before, after=after))
            output = SafetyOutput(passed=not cleaned, rewritten=cleaned)
            span.set_attribute("flagged_count", len(flagged))
        if output.passed and output.rewritten:
            raise AgentOutputError("passed=true이면 rewritten은 비어 있어야 합니다")
        self.record_trace(trace, self.name, model, output)
        return output
