# 역할: 챗봇 답변 생성 에이전트 — fact_query/metric_query/report_query/advice_request 담당 (참조: prompts/chat_answer.md)
#
# term_count/top_term은 LLM을 거치지 않는다(chat_supervisor가 템플릿으로 처리, 이 에이전트가 안 다룸).
# advice_request는 intent 감지 자체는 여전히 regex/LLM-classifier(고정 규칙)로 하지만, 실제 안내
# 문구는 2026-08-27부터 이 에이전트가 LLM으로 생성한다(윤아 요청 — "고정 문구 말고 LLM 연결해줘").
# 안전장치: banned_patterns.txt(safety_agent.py와 동일 목록)로 한 번 더 스캔해서, 조금이라도
# 조언/판단/명령 표현이 섞이면 무조건 고정 문구(ADVICE_FALLBACK_TEXT)로 되돌린다 — "관계를
# 판단하지 않는다"는 이 서비스의 핵심 원칙이라 LLM 혼자에게 맡기지 않는다.
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models.report import ChatAnswerOutput
from .base import AgentBase, AgentOutputError
from .safety_agent import load_banned_patterns

NO_RECORD_TEXT = "관련 기록을 찾지 못했어요."
_REPORT_NOT_READY_TEXT = "그 주 리포트는 아직 준비되지 않았어요."

# advice_request 고정 폴백 — LLM 생성 문구가 banned_patterns.txt에 걸리거나(안전 위반) mock
# provider일 때 사용. 기존(2026-08-27 이전) 고정 리다이렉트 문구를 그대로 유지한다.
ADVICE_FALLBACK_TEXT = (
    "이 챗봇은 대화 기록을 찾아주는 도구예요. 관계가 어떤지는 저도 판단하지 않아요. "
    "대신 요즘 대화가 어땠는지는 같이 볼 수 있어요."
)

_ADVICE_BANNED_PATTERNS = load_banned_patterns()

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
    if intent == "advice_request":
        return ChatAnswerOutput(answer=ADVICE_FALLBACK_TEXT, citations=[])
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


def _enforce_advice_safety(output: ChatAnswerOutput) -> ChatAnswerOutput:
    """advice_request는 이 서비스에서 관계를 판단하지 않는다는 원칙이 가장 직접적으로 걸린
    경로다. LLM이 만든 문장에 조언·판단·명령 표현이 하나라도 섞이면(banned_patterns.txt,
    safety_agent.py와 동일 목록) 무조건 고정 문구로 되돌린다 — citations도 항상 비운다
    (대화 인용이 아니라 안내 문구라 P-4 인용 규칙 대상이 아님)."""
    if any(pattern.search(output.answer) for pattern in _ADVICE_BANNED_PATTERNS):
        return output.model_copy(update={"answer": ADVICE_FALLBACK_TEXT, "citations": []})
    if output.citations:
        return output.model_copy(update={"citations": []})
    return output


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
            if intent == "advice_request":
                output = _enforce_advice_safety(output)
            span.set_attribute("citation_count", len(output.citations))
        return output
