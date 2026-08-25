"""메모리 지식 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def search_knowledge(
    metric: str,
    direction: str,
    k: int = 5,
    *,
    knowledge: Knowledge,
) -> list[dict]:
    """(metric, direction)에 맞는 해석 근거 문서를 최대 k개 조회한다.

    InterpretAgent의 sources는 이 함수가 반환한 문서 안에서만 사용한다.
    """
    with tracer.start_as_current_span("tool.search_knowledge") as span:
        span.set_attribute("metric", metric)
        span.set_attribute("direction", direction)

        docs = [
            dict(item)
            for item in knowledge.search(metric, direction, k)
        ]

        span.set_attribute("hits", len(docs))
        return docs