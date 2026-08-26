# 역할: 챗봇 intent 분류 에이전트 (참조: FR-006, API_SPEC §6.1, prompts/chat_intent.md)
#
# term_count/advice_request는 chat_supervisor가 정규식으로 먼저 걸러서 대부분 여기까지 안 온다 —
# 그래도 프롬프트가 5개 값을 스키마로 두는 이유는 애매한 케이스의 안전망(chat_intent.md 경계 규칙).
from __future__ import annotations

import re
from typing import Any

from ..models.report import ChatIntent, ChatIntentOutput
from .base import AgentBase

# chat_intent.md의 판별 힌트를 그대로 정규식화 — mock 모드(실 LLM 없이 데모/테스트가 돌아가야 함)
# 전용 근사치다. 완벽한 분류가 목적이 아니라 결정론적 흐름 검증이 목적.
_ADVICE_HINTS = re.compile(r"(어떻게\s*해야|어떡해야|나을까|괜찮은\s*관계|화해|헤어지)")
_REPORT_HINTS = re.compile(r"(리포트|저번에\s*나온\s*제안)")
_FACT_HINTS = re.compile(r"(언제|뭐라고\s*했|얘기했|말했)")
_METRIC_HINTS = re.compile(r"(얼마나|많이|늘었|줄었|빨라졌|느려졌|자주|편이)")


def _mock_intent(message: str) -> ChatIntent:
    if _ADVICE_HINTS.search(message):
        return "advice_request"
    if _REPORT_HINTS.search(message):
        return "report_query"
    if _FACT_HINTS.search(message):
        return "fact_query"
    if _METRIC_HINTS.search(message):
        return "metric_query"
    return "other"


class ChatIntentAgent(AgentBase):
    def __init__(self, ai):
        super().__init__("chat_intent", ai, "chat_intent.md")

    async def run(self, payload: dict[str, Any]) -> ChatIntentOutput:
        with self.span() as span:
            if self.ai.provider_name == "mock":
                output = ChatIntentOutput(intent=_mock_intent(payload["message"]))
            else:
                output = await self.generate_validated(
                    payload, ChatIntentOutput, mock_key="chat_intent", max_tokens=50
                )
            span.set_attribute("intent", output.intent)
        return output
