# 역할: 지식 문서 조회 툴 — container.knowledge.search(metric, direction) 메모리 dict (참조: API_SPEC §8, ISSUE D2)
# 벡터 검색이 아니다: (metric, direction) 조합이 ~10개라 dict 조회로 충분해 Qdrant 에 두지 않았다.
from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def search_knowledge(
    knowledge: Knowledge, metric: str, direction: str, k: int = 5
) -> list[dict]:
    """(metric, direction) → [{doc, section, text, source}] 최대 k개.

    interpret 에이전트가 `sources` 로 인용할 수 있는 유일한 출처다 (P-4) — 여기 없는 문서를
    지어내면 검수(safety)에서 걸린다.
    """
    with tracer.start_as_current_span("tool.search_knowledge") as span:
        span.set_attribute("metric", metric)
        span.set_attribute("direction", direction)
        docs = knowledge.search(metric, direction, k)
        span.set_attribute("hits", len(docs))
        return docs
