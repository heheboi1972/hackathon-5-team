"""메모리 템플릿 dict를 조회하는 에이전트 tool."""

from __future__ import annotations

from ..services.knowledge import Knowledge
from . import tracer


def get_suggestion_templates(
    *args: object,
    knowledge: Knowledge | None = None,
) -> list[dict]:
    """(metric, direction)에 맞는 제안 템플릿을 조회한다.

    두 호출 방식을 모두 지원한다.

    1. 직접 호출:
       get_suggestion_templates(knowledge, metric, direction)

    2. 의존성 주입 후 호출:
       partial(get_suggestion_templates, knowledge=knowledge)
       -> tool(metric, direction)
    """
    if knowledge is None:
        if len(args) != 3:
            raise TypeError(
                "get_suggestion_templates는 "
                "(knowledge, metric, direction) 형식으로 호출해야 합니다."
            )

        knowledge_arg = args[0]
        metric_arg = args[1]
        direction_arg = args[2]

        if not isinstance(knowledge_arg, Knowledge):
            raise TypeError("첫 번째 인자는 Knowledge여야 합니다.")

        knowledge_obj = knowledge_arg

    else:
        if len(args) != 2:
            raise TypeError(
                "knowledge 주입 시 "
                "get_suggestion_templates(metric, direction) 형식으로 호출해야 합니다."
            )

        knowledge_obj = knowledge
        metric_arg = args[0]
        direction_arg = args[1]

    if not isinstance(metric_arg, str):
        raise TypeError("metric은 str이어야 합니다.")

    if not isinstance(direction_arg, str):
        raise TypeError("direction은 str이어야 합니다.")

    with tracer.start_as_current_span(
        "tool.get_suggestion_templates"
    ) as span:
        span.set_attribute("metric", metric_arg)
        span.set_attribute("direction", direction_arg)

        templates = [
            dict(item)
            for item in knowledge_obj.suggestion_templates(
                metric_arg,
                direction_arg,
            )
        ]

        span.set_attribute("hits", len(templates))
        return templates