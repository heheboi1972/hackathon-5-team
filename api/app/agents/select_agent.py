"""에이전트 1: 숫자 없는 신호와 이상치에서 최대 3개를 결정론적으로 선별한다."""

from __future__ import annotations

from typing import Any

from ..models.report import (
    MetricSignal,
    SelectInput,
    SelectedCandidate,
    SelectOutput,
)
from ..services.ai_service import AIService
from .base import AgentBase


def _rank(signal: MetricSignal, is_outlier: bool) -> tuple[int, int, str, str, str]:
    return (
        0 if is_outlier else 1,
        0 if signal.magnitude == "clear" else 1,
        signal.metric,
        signal.direction,
        signal.outlier_ref or "",
    )


def _reason(signal: MetricSignal, is_outlier: bool) -> str:
    if is_outlier and signal.valence == "positive":
        return "평소와 다른 긍정적 변화"
    if is_outlier and signal.valence == "negative":
        return "평소와 다른 부정적 변화"
    if is_outlier:
        return "평소와 다른 흐름"
    return "눈에 띄는 변화" if signal.magnitude == "clear" else "조금 달라진 흐름"


def select_candidates(
    metrics: list[dict[str, Any]],
    outliers: list[dict[str, Any]] | None = None,
    *,
    limit: int = 3,
) -> SelectOutput:
    parsed = SelectInput(metrics=metrics, outliers=outliers or [])
    ranked: list[tuple[MetricSignal, bool]] = []
    for signal, is_outlier in [
        *((item, False) for item in parsed.metrics),
        *((item, True) for item in parsed.outliers),
    ]:
        if not signal.comparable or signal.direction == "steady":
            continue
        ranked.append((signal, is_outlier))
    ranked.sort(key=lambda item: _rank(*item))

    selected: list[tuple[MetricSignal, bool]] = []
    positive = [item for item in ranked if item[1] and item[0].valence == "positive"]
    negative = [item for item in ranked if item[1] and item[0].valence == "negative"]
    if positive and negative:
        selected.extend((positive[0], negative[0]))
    for item in ranked:
        key = (item[0].metric, item[0].direction, item[0].outlier_ref)
        if any(
            (chosen.metric, chosen.direction, chosen.outlier_ref) == key
            for chosen, _ in selected
        ):
            continue
        selected.append(item)
        if len(selected) >= min(limit, 3):
            break

    return SelectOutput(
        candidates=[
            SelectedCandidate(
                metric=signal.metric,
                direction=signal.direction,
                outlier_ref=signal.outlier_ref,
                reason=_reason(signal, is_outlier),
            )
            for signal, is_outlier in selected[: min(limit, 3)]
        ]
    )


class SelectAgent(AgentBase):
    """ISSUE C1 결정에 따라 실제 provider에서도 LLM을 호출하지 않는다."""

    def __init__(self, ai: AIService):
        super().__init__("select", ai, "select.md")

    async def run(
        self,
        payload: SelectInput | dict[str, Any],
        *,
        trace: list[dict[str, Any]] | None = None,
    ) -> SelectOutput:
        model = payload if isinstance(payload, SelectInput) else SelectInput.model_validate(payload)
        with self.span() as span:
            output = select_candidates(
                [item.model_dump() for item in model.metrics],
                [item.model_dump() for item in model.outliers],
            )
            span.set_attribute("candidate_count", len(output.candidates))
        self.record_trace(trace, self.name, model, output)
        return output
