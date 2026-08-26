# 역할: 3-7 "실 LLM 전환" 중 챗봇 쪽 검증 — chat_intent_agent.py/chat_answer_agent.py를 **실제
#       에이전트 코드 경로 그대로**(agent.run()) 실 watsonx로 호출해서 확인한다. 2-9가 리포트 쪽
#       (interpret/safety)을 검증했던 것과 정확히 같은 목적·같은 패턴 — 이번엔 챗봇 쪽 나머지 절반.
#
#       Docker 없이, FastAPI 서버 없이, Postgres/Qdrant 없이 돌아간다 — chat_supervisor.py가 하는
#       "정규식 선분기 + 툴 호출"은 건너뛰고, 에이전트가 실제로 LLM을 부르는 지점만 떼어서 확인한다.
#       (term_count/advice_request는 LLM을 아예 안 쓰는 경로라 애초에 대상 아님 — chat_supervisor.py
#       주석 참고)
#
# 사용법 (레포 루트에서, 본인 PC 터미널 — venv 활성화 후, Docker/서버 켤 필요 없음):
#   python scripts/3-7_chat_agent_real_llm_test.py
#   (.env 에 AI_PROVIDER=watsonx, WATSONX_API_KEY / WATSONX_PROJECT_ID 필요 — 이미 있음)
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
RESULT_PATH = Path(__file__).resolve().parent / "3-7_chat_agent_real_llm_raw.json"

sys.path.insert(0, str(REPO_ROOT / "api"))  # app.* 를 import 하기 위함


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


# chat_intent_agent.py 테스트 4개 — chat_intent.md 자체 힌트 규칙(_mock_intent와 같은 기준)으로
# 명확하게 갈리는 문장만 골라서, 실 LLM 분류가 그 기준과 일치하는지 확인한다.
INTENT_CASES = [
    (1, "fact_query — 사실 질문", "우리 언제 제주도 얘기했어?", "fact_query"),
    (2, "metric_query — 지표 질문", "우리 요즘 질문 많이 늘었어?", "metric_query"),
    (3, "report_query — 리포트 질문", "이번주 리포트 뭐라고 나왔어?", "report_query"),
    (4, "other — 무관한 질문", "오늘 날씨 어때?", "other"),
]

# chat_answer_agent.py 테스트 3개 — 실제 chat_supervisor.py가 만드는 payload 형태 그대로.
ANSWER_CASES = [
    (
        "fact_query",
        "우리 언제 제주도 얘기했어?",
        {
            "message": "우리 언제 제주도 얘기했어?",
            "focus_range": None,
            "history": [],
            "evidence_candidates": [
                {"session_id": 1150, "at": "2026-08-10T20:12:00+09:00", "sender": "a",
                 "snippet": "다음 달에 제주도 가자!", "score": 0.82},
                {"session_id": 1151, "at": "2026-08-11T09:03:00+09:00", "sender": "b",
                 "snippet": "제주도 숙소 알아볼까?", "score": 0.77},
            ],
        },
        {"evidence_candidates_key": "evidence_candidates"},
    ),
    (
        "metric_query",
        "우리 요즘 질문 많이 늘었어?",
        {
            "message": "우리 요즘 질문 많이 늘었어?",
            "focus_range": None,
            "history": [],
            "metrics": {
                "range": {"question_rate": {"couple": 0.2, "mine": 0.1},
                          "reply_gap_median_min": {"couple": 12, "mine": 3},
                          "message_count": 145},
                "baseline": {"weeks": 8, "question_rate": {"couple": 0.23, "mine": 0.22},
                             "reply_gap_median_min": {"couple": 5, "mine": 4},
                             "message_count": 132.5},
                "comment": "평소보다 답장 간격이 뚜렷하게 길어졌어요.",
            },
        },
        {},
    ),
    (
        "report_query",
        "이번주 리포트 요약해줘",
        {
            "message": "이번주 리포트 요약해줘",
            "focus_range": None,
            "history": [],
            "report": {
                "highlights": [
                    {"id": "h1", "metric": "question_rate",
                     "observation": "질문이 늘었어요",
                     "interpretations": ["관심이 많아진 걸 수도", "요즘 대화가 늘어난 영향일 수도"]},
                ],
                "suggestions": [
                    {"id": "s1", "linked_highlight": "h1", "template_id": "t1",
                     "text": "오늘 서로 궁금한 걸 물어보면 어떨까요"},
                ],
                "moments": [],
                "status": "generated",
            },
        },
        {},
    ),
]


async def main() -> None:
    env = load_env(ENV_PATH)
    api_key = env.get("WATSONX_API_KEY", "")
    project_id = env.get("WATSONX_PROJECT_ID", "")
    url = env.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model_id = env.get("WATSONX_MODEL_ID", "openai/gpt-oss-120b")
    embedding_model_id = env.get("WATSONX_EMBEDDING_MODEL_ID", "intfloat/multilingual-e5-large")
    reasoning_effort = env.get("WATSONX_REASONING_EFFORT", "low")

    if not api_key or not project_id:
        print("[에러] .env 에 WATSONX_API_KEY / WATSONX_PROJECT_ID 가 없습니다.")
        sys.exit(1)

    from app.agents.base import AgentOutputError
    from app.agents.chat_answer_agent import ChatAnswerAgent
    from app.agents.chat_intent_agent import ChatIntentAgent
    from app.services.ai_service import WatsonxAIService

    ai = WatsonxAIService(
        api_key=api_key, url=url, project_id=project_id, model_id=model_id,
        embedding_model_id=embedding_model_id, reasoning_effort=reasoning_effort,
    )
    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort} | provider: {ai.provider_name}")
    print("=" * 70)

    results: dict[str, list[dict]] = {"chat_intent": [], "chat_answer": []}
    total_ok = 0
    total_n = 0

    # --- chat_intent_agent.py ---
    print("\n[chat_intent_agent.py] — 실제 ChatIntentAgent.run() 경로, 4개 케이스")
    intent_agent = ChatIntentAgent(ai)
    for idx, label, message, expected in INTENT_CASES:
        record: dict = {"index": idx, "label": label, "message": message, "expected": expected}
        try:
            output = await intent_agent.run({"message": message, "focus_range": None, "history": []})
            record["actual"] = output.intent
            record["ok"] = output.intent == expected
            record["problems"] = [] if record["ok"] else [
                f"기대={expected!r} 실제={output.intent!r}"
            ]
        except AgentOutputError as e:
            record["ok"] = False
            record["problems"] = [f"AgentOutputError: {e}"]
        except Exception as e:
            record["ok"] = False
            record["problems"] = [f"{type(e).__name__}: {e}"]
        results["chat_intent"].append(record)
        total_n += 1
        total_ok += int(record["ok"])
        mark = "✓" if record["ok"] else "✗"
        print(f"  [{mark}] 입력 {idx} — {label}")
        for p in record["problems"]:
            print(f"        - {p}")

    # --- chat_answer_agent.py ---
    print("\n[chat_answer_agent.py] — 실제 ChatAnswerAgent.run() 경로, 3개 intent")
    answer_agent = ChatAnswerAgent(ai)
    for intent, label, payload, meta in ANSWER_CASES:
        record = {"intent": intent, "label": label}
        candidates = payload.get(meta.get("evidence_candidates_key", "")) if meta else None
        try:
            output = await answer_agent.run(intent, payload, candidates=candidates)
            problems = []
            if not output.answer.strip():
                problems.append("answer가 비어있음")
            if intent == "fact_query" and not output.citations:
                problems.append(f"citations가 비어서 code가 폴백 처리함(정상 동작일 수도): {output.answer!r}")
            record = {
                "ok": len(problems) == 0,
                "output": output.model_dump(mode="json"),
                "problems": problems,
            }
        except AgentOutputError as e:
            record = {"ok": False, "problems": [f"AgentOutputError: {e}"]}
        except Exception as e:
            record = {"ok": False, "problems": [f"{type(e).__name__}: {e}"]}
        results["chat_answer"].append({"intent": intent, "label": label, **record})
        total_n += 1
        total_ok += int(record.get("ok", False))
        mark = "✓" if record.get("ok") else "✗"
        print(f"  [{mark}] {intent} — {label}")
        if record.get("output"):
            print(f"        answer: {record['output']['answer']!r}")
        for p in record.get("problems", []):
            print(f"        - {p}")

    print("=" * 70)
    print(f"전체: {total_ok}/{total_n} 통과")
    print("\n※ 여기서 통과했다는 건 챗봇 쪽 실 LLM 연결(3-7의 나머지 절반)이 response_format을")
    print("   포함해 끝까지 동작한다는 뜻입니다. Docker/DB 없이도 확인 가능한 부분까지 검증됨 —")
    print("   실제 검색 결과(search_conversation)/실 지표(get_metrics)를 넣는 통합 테스트는")
    print("   업로드→리포트 파이프라인이 실제로 돌아간 뒤 별도로 확인해야 합니다.")

    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
