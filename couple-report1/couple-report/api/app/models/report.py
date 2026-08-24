"""리포트 에이전트 간 JSON 계약의 최소 모델."""

from typing import Any

from pydantic import BaseModel, Field


class StoredReport(BaseModel):
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    moments: list[dict[str, Any]] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=lambda: {"passed": True, "rewritten": []})

