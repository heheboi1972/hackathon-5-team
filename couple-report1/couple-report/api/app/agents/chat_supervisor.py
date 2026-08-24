"""챗 intent→도구→인용 정책의 Mock supervisor."""

from typing import Any


class ChatSupervisor:
    async def run(self, message: str) -> dict[str, Any]:
        return {"intent": "other", "answer": message, "citations": []}

