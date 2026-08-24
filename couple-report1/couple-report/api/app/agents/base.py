"""에이전트 공통 Mock 인터페이스. 실제 프롬프트/OTel은 후속 구현 대상."""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentResult:
    output: dict[str, Any]
    trace: list[dict[str, Any]]


class BaseAgent:
    name = "base"

    async def run(self, payload: dict[str, Any]) -> AgentResult:
        return AgentResult(output=payload, trace=[{"agent": self.name, "provider": "mock"}])

