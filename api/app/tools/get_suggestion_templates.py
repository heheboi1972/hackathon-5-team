# 역할: 제안 템플릿 조회 툴 — container.knowledge.suggestion_templates(metric, direction) 메모리 dict
#      (참조: API_SPEC §8, ISSUE D2)
from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def get_suggestion_templates(
    knowledge: Knowledge, metric: str, direction: str
) -> list[dict]:
    """(metric, direction) → [{template_id, text}].

    suggest 에이전트는 이 목록에서 **고르기만** 한다 — 자유 생성 금지(REQUIREMENTS FR-004).
    그래서 응답의 `template_id` 는 항상 templates.json 에 존재한다 (TC-API-005-8).
    """
    with tracer.start_as_current_span("tool.get_suggestion_templates") as span:
        span.set_attribute("metric", metric)
        span.set_attribute("direction", direction)
        templates = knowledge.suggestion_templates(metric, direction)
        span.set_attribute("hits", len(templates))
        return templates
