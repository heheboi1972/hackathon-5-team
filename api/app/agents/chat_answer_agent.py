# 역할: 챗봇 답변 생성 에이전트 — fact_query/metric_query/report_query 전용 (참조: prompts/chat_answer.md)
#
# term_count/advice_request는 LLM을 거치지 않으므로(chat_supervisor가 처리) 이 에이전트가 다루지 않는다.
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models.report import ChatAnswerOutput
from .base import AgentBase, AgentOutputError

NO_RECORD_TEXT = "관련 기록을 찾지 못했어요."
_REPORT_NOT_READY_TEXT = "그 주 리포트는 아직 준비되지 않았어요."

# evidence/citations 처럼 "항상 객체 배열"이 깨지면 안 되는 출력이라 구조화 출력을 쓴다
# (interpret_agent.py와 같은 근거 — scripts/2-6b_response_format_test.py, 2026-08-25 윤아).
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "chat_answer_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "integer"},
                            "at": {"type": "string"},
                            "sender": {"type": "string", "enum": ["a", "b"]},
                            "snippet": {"type": "string"},
                        },
                        "required": ["session_id", "at", "sender", "snippet"],
                        "additionalProperties": False,
                    },
                },
                "metrics": {"type": ["object", "null"]},
            },
            "required": ["answer", "citations"],
            "additionalProperties": False,
        },
    },
}


def _mock_answer(intent: str, payload: dict[str, Any]) -> ChatAnswerOutput:
    if intent == "fact_query":
        candidates = payload.get("evidence_candidates") or []
        if not candidates:
            return ChatAnswerOutput(answer=NO_RECORD_TEXT, citations=[])
        top = candidates[0]
        citation = {k: top[k] for k in ("session_id", "at", "sender", "snippet")}
        return ChatAnswerOutput(
            answer=f"{top['at']} 대화에서 관련 내용을 찾았어요: '{top['snippet']}'",
            citations=[citation],
        )
    if intent == "metric_query":
        comment = (payload.get("metrics") or {}).get("comment", "")
        return ChatAnswerOutput(answer=comment, citations=[])
    # report_query
    report = payload.get("report")
    if not report or not report.get("highlights"):
        return ChatAnswerOutput(answer=_REPORT_NOT_READY_TEXT, citations=[])
    highlight = report["highlights"][0]
    return ChatAnswerOutput(answer=highlight["observation"], citations=[])


def _validate_fact_grounding(
    output: ChatAnswerOutput, candidates: list[dict[str, Any]]
) -> None:
    """P-4: 인용은 search_conversation이 실제로 준 후보 밖에서 만들면 안 된다."""
    allowed = {
        (item["session_id"], item["at"], item["snippet"]) for item in candidates
    }
    for citation in output.citations:
        key = (citation.session_id, citation.at, citation.snippet)
        if key not in allowed:
            raise AgentOutputError("search_conversation 밖의 citation이 있습니다")


class ChatAnswerAgent(AgentBase):
    def __init__(self, ai):
        super().__init__("chat_answer", ai, "chat_answer.md")

    async def run(
        self,
        intent: str,
        payload: dict[str, Any],
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> ChatAnswerOutput:
        with self.span() as span:
            if self.ai.provider_name == "mock":
                output = _mock_answer(intent, payload)
            else:
                output = await self.generate_validated(
                    payload,
                    ChatAnswerOutput,
                    mock_key=f"chat_answer_{intent}",
                    response_format=_RESPONSE_FORMAT,
                )
            if intent == "fact_query":
                if candidates:
                    _validate_fact_grounding(output, candidates)
                if not output.citations:
                    output = output.model_copy(update={"answer": NO_RECORD_TEXT})
            span.set_attribute("citation_count", len(output.citations))
        return output
