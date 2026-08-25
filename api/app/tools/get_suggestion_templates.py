"""메모리 템플릿 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge


def get_suggestion_templates(
    metric: str, direction: str, *, knowledge: Knowledge
) -> list[dict]:
    return [dict(item) for item in knowledge.suggestion_templates(metric, direction)]
