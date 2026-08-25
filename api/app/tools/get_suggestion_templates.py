"""메모리 템플릿 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def get_suggestion_templates(
    metric: str,
    direction: str,
    *,
    knowledge: Knowledge,
) -> list[dict]:
    """(metric, direction)에 맞는 제안 템플릿을 조회한다.

    SuggestAgent는 이 목록에서 템플릿을 선택하며 자유 생성하지 않는다.
    따라서 응답의 template_id는 templates.json에 존재해야 한다.
    """
    with tracer.start_as_current_span("tool.get_suggestion_templates") as span:
        span.set_attribute("metric", metric)
        span.set_attribute("direction", direction)

        templates = [
            dict(item)
            for item in knowledge.suggestion_templates(metric, direction)
        ]

        span.set_attribute("hits", len(templates))
        return templates