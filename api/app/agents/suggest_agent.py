"""에이전트 3: tool이 반환한 템플릿만 골라 그대로 제안한다."""

from __future__ import annotations

import re
from typing import Any, Callable

from ..models.report import (
    AgentSuggestion,
    SuggestInput,
    SuggestionTemplate,
    SuggestOutput,
)
from ..services.ai_service import AIService
from .base import AgentBase, AgentOutputError, maybe_await

Tool = Callable[..., Any]
_COMMAND_RE = re.compile(r"(?:하세요|해보세요|하셔야|해야\s*(?:해|합니다|해요))")


def _one_sentence(text: str) -> bool:
    stripped = text.strip()
    inner = stripped.rstrip(".!?。")
    return bool(stripped) and not re.search(r"[.!?。]", inner)


class SuggestAgent(AgentBase):
    """템플릿 선택은 결정론적이므로 provider와 무관하게 LLM을 호출하지 않는다."""

    def __init__(self, ai: AIService, get_suggestion_templates: Tool):
        super().__init__("suggest", ai, "suggest.md")
        self.get_suggestion_templates = get_suggestion_templates

    async def run(
        self,
        payload: SuggestInput | dict[str, Any],
        *,
        trace: list[dict[str, Any]] | None = None,
    ) -> SuggestOutput:
        model = payload if isinstance(payload, SuggestInput) else SuggestInput.model_validate(payload)
        with self.span() as span:
            raw_templates = await maybe_await(
                self.get_suggestion_templates(model.metric, model.direction)
            )
            templates = sorted(
                (SuggestionTemplate.model_validate(item) for item in (raw_templates or [])),
                key=lambda item: item.template_id,
            )
            usable = [
                item
                for item in templates
                if not _COMMAND_RE.search(item.text) and _one_sentence(item.text)
            ][:2]
            if not usable:
                raise AgentOutputError("사용 가능한 제안 템플릿이 없습니다")
            output = SuggestOutput(
                suggestions=[
                    AgentSuggestion(
                        linked_highlight=model.linked_highlight,
                        template_id=item.template_id,
                        text=item.text,
                    )
                    for item in usable
                ]
            )
            span.set_attribute("template_count", len(templates))
        trace_input = {
            **model.model_dump(mode="json"),
            "templates": [item.model_dump(mode="json") for item in templates],
        }
        self.record_trace(trace, self.name, trace_input, output)
        return output
