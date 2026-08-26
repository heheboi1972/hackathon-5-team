"""주간 저장 지표를 네 에이전트의 엄격한 계약으로 조립한다."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from ..models.report import InterpretInput, SafetyInput, SelectInput, SuggestInput
from ..services.metrics import agent_metric_input

SELECTABLE_AGENT_METRICS = frozenset(
    {
        "question_rate",
        "message_length_median",
        "reply_gap_median_min",
        "resume_delay_median_min",
        "session_length_median",
    }
)
_OUTLIER_METRIC_ALIASES = {
    "reply_gap": "reply_gap_median_min",
    "resume_delay": "resume_delay_median_min",
    "session_length": "session_length_median",
}


def canonical_agent_metric(metric: str) -> str | None:
    canonical = _OUTLIER_METRIC_ALIASES.get(metric, metric)
    return canonical if canonical in SELECTABLE_AGENT_METRICS else None

class ReportGenerationError(RuntimeError):
    def __init__(self, message: str, *, trace_id: str, execution_trace: list[dict[str, Any]]):
        super().__init__(message)
        self.trace_id = trace_id
        self.execution_trace = execution_trace


def _step(name: str, status: str, input_summary: dict[str, Any] | None = None,
          output_summary: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    return {"step": name, "status": status, "input": input_summary or {},
            "output": output_summary or {}, "error": error}


def _outlier_signals(outliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals = []
    for index, item in enumerate(outliers):
        metric = canonical_agent_metric(str(item.get("metric", "")))
        if metric is None:
            continue
        direction = item.get("direction")
        if direction not in {"high", "low", "up", "down"}:
            continue
        signals.append({
            "metric": metric,
            "direction": "up" if direction in {"high", "up"} else "down",
            "magnitude": "clear", "comparable": True,
            "outlier_ref": f"outlier:{index}",
            "valence": item.get("valence", "neutral"),
        })
    return signals


def _moments(outliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in outliers:
        if not item.get("at") or item.get("session_id") is None:
            continue
        moment = {
            "kind": item.get("metric", "outlier"), "at": item["at"],
            "session_id": item["session_id"],
            "value_min": item.get("value_min", item.get("value")),
            "baseline_median_min": item.get("baseline_median_min", item.get("baseline_median")),
            "text": "평소와 다른 대화 흐름이 포착된 순간이에요",
        }
        if "who" in item:
            moment["who"] = item["who"]
        result.append(moment)
    return result


def _apply_rewrites(highlights: list[dict[str, Any]], suggestions: list[dict[str, Any]],
                    rewrites: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = {item.before: item.after for item in rewrites}
    safe_highlights, valid_ids = [], set()
    for item in highlights:
        candidate = deepcopy(item)
        candidate["observation"] = mapping.get(candidate["observation"], candidate["observation"])
        candidate["interpretations"] = [mapping.get(text, text) for text in candidate["interpretations"]
                                          if mapping.get(text, text)]
        if candidate["observation"] and len(candidate["interpretations"]) >= 2:
            safe_highlights.append(candidate)
            valid_ids.add(candidate["id"])
    safe_suggestions = []
    for item in suggestions:
        text = mapping.get(item["text"], item["text"])
        if text and item["linked_highlight"] in valid_ids:
            safe_suggestions.append({**item, "text": text})
    return safe_highlights, safe_suggestions


class ReportSupervisor:
    def __init__(self, select_agent: Any, interpret_agent: Any, suggest_agent: Any,
                 safety_agent: Any):
        self.select = select_agent
        self.interpret = interpret_agent
        self.suggest = suggest_agent
        self.safety = safety_agent

    async def run(self, row: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(uuid4())
        trace: list[dict[str, Any]] = []
        metrics, outliers = row.get("metrics") or {}, row.get("outliers") or []
        base = {"week_start": str(row["week_start"]), "summary": row.get("summary"),
                "metrics": metrics, "weekly_terms": row.get("weekly_terms", {}),
                "highlights": [], "suggestions": [], "moments": _moments(outliers),
                "safety": {"passed": True, "rewritten": []}}
        comparable = any(isinstance(value, dict) and value.get("comparable")
                         for value in metrics.values())
        trace.append(_step("baseline_check", "ok", {"metric_count": len(metrics)},
                           {"comparable": comparable}))
        if not comparable:
            return {"status": "insufficient_baseline",
                    "report": {**base, "status": "insufficient_baseline"},
                    "trace_id": trace_id, "execution_trace": trace}
        try:
            current_step = "select"
            metric_signals = agent_metric_input(metrics)
            selected = await self.select.run(SelectInput(
                metrics=metric_signals, outliers=_outlier_signals(outliers)))
            trace.append(_step("select", "ok", {"metric_count": len(metric_signals),
                                                 "outlier_count": len(outliers)},
                               {"candidate_count": len(selected.candidates)}))
            magnitude = {item["metric"]: item["magnitude"] for item in metric_signals}
            highlights, suggestions = [], []
            for index, candidate in enumerate(selected.candidates, 1):
                highlight_id = f"h{index}"
                current_step = "interpret"
                interpreted = await self.interpret.run(InterpretInput(
                    couple_id=row["couple_id"], metric=candidate.metric,
                    direction=candidate.direction, magnitude=magnitude.get(candidate.metric, "clear"),
                    outlier_ref=candidate.outlier_ref))
                for output in interpreted.highlights:
                    highlights.append({"id": highlight_id, "metric": candidate.metric,
                                       **output.model_dump(mode="json"), "sentiment": "neutral"})
                trace.append(_step("interpret", "ok", {"metric": candidate.metric},
                                   {"highlight_count": len(interpreted.highlights)}))
                current_step = "suggest"
                suggested = await self.suggest.run(SuggestInput(
                    metric=candidate.metric, direction=candidate.direction,
                    magnitude=magnitude.get(candidate.metric, "clear"),
                    linked_highlight=highlight_id))
                for output in suggested.suggestions:
                    suggestions.append({"id": f"s{len(suggestions) + 1}",
                                        **output.model_dump(mode="json")})
                trace.append(_step("suggest", "ok", {"metric": candidate.metric},
                                   {"suggestion_count": len(suggested.suggestions)}))
            current_step = "safety"
            safety = await self.safety.run(SafetyInput(highlights=highlights,
                                                       suggestions=suggestions,
                                                       moments=base["moments"]))
            highlights, suggestions = _apply_rewrites(highlights, suggestions, safety.rewritten)
            trace.append(_step("safety", "ok", {"sentence_groups": len(highlights) + len(suggestions)},
                               {"passed": safety.passed, "rewrite_count": len(safety.rewritten)}))
            report = {**base, "status": "generated", "highlights": highlights,
                      "suggestions": suggestions, "safety": safety.model_dump(mode="json")}
            return {"status": "generated", "report": report, "trace_id": trace_id,
                    "execution_trace": trace}
        except Exception as exc:
            trace.append(_step(current_step, "failed", error=str(exc)[:1000]))
            raise ReportGenerationError(str(exc), trace_id=trace_id,
                                        execution_trace=trace) from exc
