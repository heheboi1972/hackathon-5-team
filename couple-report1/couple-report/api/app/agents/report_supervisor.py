"""선별→해석→제안→검수 실행 순서의 Mock supervisor."""

from typing import Any


class ReportSupervisor:
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"provider": "mock", "input": payload, "highlights": [], "suggestions": []}

