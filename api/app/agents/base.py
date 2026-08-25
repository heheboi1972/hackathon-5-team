"""에이전트 공통 실행기: prompt, schema 검증, 1회 재시도, trace, OTel."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..models.report import AgentTraceStep
from ..services.ai_service import AIService, AIServiceError

try:
    from opentelemetry import trace

    _tracer = trace.get_tracer("couple-report")
except Exception:  # pragma: no cover - 선택 의존성
    class _NoopSpan:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def set_attribute(self, *_args, **_kwargs):
            return None

    class _NoopTracer:
        def start_as_current_span(self, *_args, **_kwargs):
            return _NoopSpan()

    _tracer = _NoopTracer()


OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentOutputError(RuntimeError):
    """LLM JSON 또는 도메인 불변 규칙이 유효하지 않을 때 발생한다."""


async def maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class AgentBase:
    """실제 LLM 경로의 공통 경계. 총 호출은 최초 1회 + 재시도 1회다."""

    def __init__(self, name: str, ai: AIService, prompt_name: str):
        self.name = name
        self.ai = ai
        self.prompt_path = (
            Path(__file__).resolve().parents[1] / "prompts" / prompt_name
        )

    def prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def span(self):
        return _tracer.start_as_current_span(f"agent.{self.name}")

    @staticmethod
    def record_trace(
        trace_steps: list[dict[str, Any]] | None,
        agent: str,
        input_data: BaseModel | dict[str, Any],
        output_data: BaseModel | dict[str, Any],
    ) -> None:
        if trace_steps is None:
            return
        raw_input = (
            input_data.model_dump(mode="json")
            if isinstance(input_data, BaseModel)
            else input_data
        )
        raw_output = (
            output_data.model_dump(mode="json")
            if isinstance(output_data, BaseModel)
            else output_data
        )
        step = AgentTraceStep(agent=agent, input=raw_input, output=raw_output)
        trace_steps.append(step.model_dump(mode="json"))

    async def generate_validated(
        self,
        payload: dict[str, Any],
        output_model: type[OutputT],
        *,
        mock_key: str,
        max_tokens: int = 2000,
    ) -> OutputT:
        messages = [
            {"role": "system", "content": self.prompt()},
            {"role": "user", "content": _json(payload)},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                raw = await self.ai.generate_json(
                    messages, max_tokens=max_tokens, mock_key=mock_key
                )
                return output_model.model_validate(raw)
            except (AIServiceError, ValidationError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "이전 출력이 JSON 스키마를 통과하지 못했습니다. "
                                "프롬프트의 출력 계약에 맞는 JSON만 한 번 다시 반환하세요."
                            ),
                        }
                    )
        raise AgentOutputError(
            f"{self.name} 출력 검증 실패 (최대 2회 호출): {last_error}"
        ) from last_error


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
