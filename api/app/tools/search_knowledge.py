"""메모리 지식 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge


def search_knowledge(
    metric: str, direction: str, k: int = 5, *, knowledge: Knowledge
) -> list[dict]:
    return [dict(item) for item in knowledge.search(metric, direction, k)]
