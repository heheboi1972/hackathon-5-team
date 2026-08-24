"""리포트 안전 검수 에이전트 Mock."""

from app.agents.base import BaseAgent


class SafetyAgent(BaseAgent):
    name = "safety"

