"""저장형의 a/b 값을 API 응답형 couple/mine으로 투영하는 최소 함수."""

from typing import Any, Literal


def project_pair(value: dict[str, Any], member: Literal["a", "b"]) -> dict[str, Any]:
    return {"couple": value.get("couple"), "mine": value.get(member)}

