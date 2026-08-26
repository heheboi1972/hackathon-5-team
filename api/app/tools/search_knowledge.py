"""메모리 지식 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def search_knowledge(
    *args: object,
    knowledge: Knowledge | None = None,
    k: int = 5,
) -> list[dict]:
    """(metric, direction)에 맞는 해석 근거 문서를 최대 k개 조회한다.

    두 호출 방식을 모두 지원한다.

    1. 직접 호출:
       search_knowledge(knowledge, metric, direction, k=5)

    2. 의존성 주입 후 호출:
       partial(search_knowledge, knowledge=knowledge)
       -> tool(metric, direction, 5)
    """
    if knowledge is None:
        if len(args) not in {3, 4}:
            raise TypeError(
                "search_knowledge는 "
                "(knowledge, metric, direction, k=5) 형식으로 호출해야 합니다."
            )

        knowledge_arg = args[0]
        metric_arg = args[1]
        direction_arg = args[2]

        if not isinstance(knowledge_arg, Knowledge):
            raise TypeError("첫 번째 인자는 Knowledge여야 합니다.")

        knowledge_obj = knowledge_arg

        if len(args) == 4:
            k_arg = args[3]
            if not isinstance(k_arg, int):
                raise TypeError("k는 int여야 합니다.")
            k = k_arg

    else:
        if len(args) not in {2, 3}:
            raise TypeError(
                "knowledge 주입 시 "
                "search_knowledge(metric, direction, k=5) 형식으로 호출해야 합니다."
            )

        knowledge_obj = knowledge
        metric_arg = args[0]
        direction_arg = args[1]

        if len(args) == 3:
            k_arg = args[2]
            if not isinstance(k_arg, int):
                raise TypeError("k는 int여야 합니다.")
            k = k_arg

    if not isinstance(metric_arg, str):
        raise TypeError("metric은 str이어야 합니다.")

    if not isinstance(direction_arg, str):
        raise TypeError("direction은 str이어야 합니다.")

    with tracer.start_as_current_span("tool.search_knowledge") as span:
        span.set_attribute("metric", metric_arg)
        span.set_attribute("direction", direction_arg)

        docs = [
            dict(item)
            for item in knowledge_obj.search(
                metric_arg,
                direction_arg,
                k,
            )
        ]

        span.set_attribute("hits", len(docs))
        return docs