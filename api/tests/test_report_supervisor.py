"""TASKS 3-4 supervisor 오케스트레이션 계약."""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from app.agents.interpret_agent import InterpretAgent
from app.agents.report_supervisor import ReportSupervisor
from app.agents.safety_agent import SafetyAgent
from app.agents.select_agent import SelectAgent
from app.agents.suggest_agent import SuggestAgent


class _AI:
    provider_name = "mock"


def _row(comparable=True):
    metric = {"couple": 8, "a": 7, "b": 9, "baseline_couple": 12,
              "baseline_a": 11, "baseline_b": 13, "delta_couple": -4,
              "delta_a": -4, "delta_b": -4, "comparable": comparable}
    return {"couple_id": uuid4(), "week_start": date(2026, 8, 17),
            "summary": {"question_rate": {"couple": 8, "a": 7, "b": 9}},
            "metrics": {"question_rate": metric}, "outliers": [],
            "weekly_terms": {"a": {"pos": [], "neg": []}, "b": {"pos": [], "neg": []}}}


def _supervisor():
    async def conversation(*_args):
        return [{"session_id": 1, "at": datetime(2026, 8, 17, tzinfo=timezone.utc),
                 "sender": "a", "snippet": "오늘은 어땠어", "score": 0.9}]

    def knowledge(*_args):
        return [{"doc": "guide", "section": "questions", "text": "context"}]

    def templates(*_args):
        return [{"template_id": "q-down-1", "text": "서로 궁금했던 순간을 가볍게 나눠보면 어떨까요"}]

    ai = _AI()
    return ReportSupervisor(SelectAgent(ai), InterpretAgent(ai, conversation, knowledge),
                            SuggestAgent(ai, templates), SafetyAgent(ai))


def test_generated_report_runs_agents_and_keeps_storage_axes_out_of_llm_trace():
    result = asyncio.run(_supervisor().run(_row()))
    assert result["status"] == "generated"
    assert result["report"]["highlights"]
    assert len(result["report"]["highlights"][0]["interpretations"]) >= 2
    assert result["report"]["suggestions"][0]["template_id"] == "q-down-1"
    assert [step["step"] for step in result["execution_trace"]] == [
        "baseline_check", "select", "interpret", "suggest", "safety"]
    trace_text = str(result["execution_trace"])
    assert "오늘은 어땠어" not in trace_text
    assert "'a':" not in trace_text and "'b':" not in trace_text


def test_insufficient_baseline_short_circuits_every_agent():
    class Bomb:
        async def run(self, *_args, **_kwargs):
            raise AssertionError("agent must not run")

    result = asyncio.run(ReportSupervisor(Bomb(), Bomb(), Bomb(), Bomb()).run(_row(False)))
    assert result["status"] == "insufficient_baseline"
    assert result["report"]["highlights"] == []
    assert [step["step"] for step in result["execution_trace"]] == ["baseline_check"]


def test_agent_failure_records_exact_step_without_retry_loop():
    class Select:
        calls = 0
        async def run(self, *_args, **_kwargs):
            self.calls += 1
            raise ValueError("invalid agent output")

    select = Select()
    async def scenario():
        from app.agents.report_supervisor import ReportGenerationError
        try:
            await ReportSupervisor(select, object(), object(), object()).run(_row())
        except ReportGenerationError as exc:
            assert exc.execution_trace[-1]["step"] == "select"
            assert exc.execution_trace[-1]["status"] == "failed"
        else:
            raise AssertionError("ReportGenerationError expected")
    asyncio.run(scenario())
    assert select.calls == 1
