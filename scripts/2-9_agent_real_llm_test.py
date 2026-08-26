# 역할: 3-7 "실 LLM 연결" 검증 — interpret_agent.py/safety_agent.py를 **실제 에이전트 코드
#       경로 그대로**(agent.run()) 실 watsonx로 호출해서, response_format 포함 전체 파이프라인이
#       진짜로 동작하는지 확인한다. 2-6b/2-8은 프롬프트 문자열만 떼어내 API를 직접 불렀지만,
#       이번엔 AgentBase.generate_validated() → _validate_language()/_validate_grounding() →
#       Pydantic 검증까지 실제 코드가 하는 그대로 통과시킨다.
#
#       select_agent.py/suggest_agent.py는 여기 없음 — LLM을 아예 안 쓰는 결정론적 코드로
#       이미 확정됐기 때문(2-8 스크립트 하단 "제외 사유" 참고). "실 LLM 연결"이 의미 있는 건
#       interpret/safety 둘뿐.
#
#       chat_supervisor.py/tools/get_metrics.py 쪽(3-7의 챗봇 부분)은 아직 스텁이라 이 스크립트로
#       검증 못 함 — 윤석 쪽 구현 뒤에 별도 스크립트 필요.
#
# 사용법 (레포 루트에서, 본인 PC 터미널 — venv 활성화 후):
#   python scripts/2-9_agent_real_llm_test.py
#   (.env 에 AI_PROVIDER=watsonx, WATSONX_API_KEY / WATSONX_PROJECT_ID 필요)
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
RESULT_PATH = Path(__file__).resolve().parent / "2-9_agent_real_llm_raw.json"

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


COUPLE_ID = UUID("11111111-1111-1111-1111-111111111111")

# interpret_agent.py 테스트 입력 5개 — 2-6b의 10개 중 근거 있음/없음/이전에 문제였던 10번을 골라 축약.
INTERPRET_CASES = [
    (1, "질문 빈도 증가 (눈에 띄게, 근거·지식 있음)", {
        "couple_id": COUPLE_ID, "metric": "question_rate", "direction": "up", "magnitude": "clear",
    }, {
        "evidence": [{"session_id": 1150, "at": "2026-08-10T20:12:00+09:00", "sender": "a", "snippet": "너 요즘 취미 뭐야?", "score": 0.8}],
        "knowledge": [{"doc": "question_rate_up.md", "section": "", "text": "", "source": "couple-report 팀 작성"}],
    }),
    (2, "메시지 길이 감소 — 근거·지식 후보 없음", {
        "couple_id": COUPLE_ID, "metric": "message_length_median", "direction": "down", "magnitude": "slight",
    }, {"evidence": [], "knowledge": []}),
    (3, "답장 간격 증가 (눈에 띄게)", {
        "couple_id": COUPLE_ID, "metric": "reply_gap_median_min", "direction": "up", "magnitude": "clear",
    }, {
        "evidence": [{"session_id": 1187, "at": "2026-08-19T23:41:00+09:00", "sender": "b", "snippet": "미안 지금 봤어", "score": 0.75}],
        "knowledge": [{"doc": "reply_gap_median_min_up_01.md", "section": "", "text": "", "source": "couple-report 팀 작성"}],
    }),
    (4, "대화 재개 지연 감소 (약하게)", {
        "couple_id": COUPLE_ID, "metric": "resume_delay_median_min", "direction": "down", "magnitude": "slight",
    }, {
        "evidence": [{"session_id": 1245, "at": "2026-08-22T19:00:00+09:00", "sender": "a", "snippet": "바로 답장왔네", "score": 0.7}],
        "knowledge": [],
    }),
    (10, "메시지 길이 감소 — 1차·2차 테스트 모두에서 evidence/sources가 문자열로 축약됐던 케이스", {
        "couple_id": COUPLE_ID, "metric": "message_length_median", "direction": "down", "magnitude": "clear",
    }, {
        "evidence": [{"session_id": 1320, "at": "2026-08-20T23:50:00+09:00", "sender": "b", "snippet": "응", "score": 0.6}],
        "knowledge": [{"doc": "message_length_median_down.md", "section": "", "text": "", "source": "couple-report 팀 작성"}],
    }),
]

# safety_agent.py 테스트 — 2-8과 같은 6문장을, 실제 SafetyInput 필드 구조(observation/interpretations/
# highlights/suggestions)에 나눠 담아서 규칙기반 사전 필터(_is_banned) → 실 LLM 재작성 → 재검사까지
# 진짜 에이전트 흐름 그대로 태운다.
SAFETY_PAYLOAD = {
    "observation": "A가 질문을 많이 했어요",
    "interpretations": ["B보다 A가 더 자주 답장했어요"],
    "highlights": [
        {
            "id": "h1",
            "metric": "question_rate",
            "observation": "질문이 30% 늘었어요",
            "interpretations": ["관계 온도 B등급이에요"],
        }
    ],
    "suggestions": [
        {"id": "s1", "linked_highlight": "h1", "template_id": "t1", "text": "더 자주 연락하세요"},
        {"id": "s2", "linked_highlight": "h1", "template_id": "t2", "text": "이 정도면 헤어지는 게 나을까 싶어요"},
    ],
    "moments": [],
}


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
    from app.agents.interpret_agent import InterpretAgent
    from app.agents.safety_agent import SafetyAgent
    from app.services.ai_service import WatsonxAIService

    ai = WatsonxAIService(
        api_key=api_key, url=url, project_id=project_id, model_id=model_id,
        embedding_model_id=embedding_model_id, reasoning_effort=reasoning_effort,
    )
    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort} | provider: {ai.provider_name}")
    print("=" * 70)

    results: dict[str, list[dict]] = {"interpret": [], "safety": []}
    total_ok = 0
    total_n = 0

    # --- interpret_agent.py ---
    print("\n[interpret_agent.py] — 실제 InterpretAgent.run() 경로, 5개 케이스")
    for idx, label, payload, tool_data in INTERPRET_CASES:

        async def search_conversation(*_a, **_k):
            return tool_data["evidence"]

        async def search_knowledge(*_a, **_k):
            return tool_data["knowledge"]

        agent = InterpretAgent(ai, search_conversation, search_knowledge)
        record: dict = {"index": idx, "label": label}
        try:
            output = await agent.run(payload)
            record["ok"] = True
            record["output"] = output.model_dump(mode="json")
            record["problems"] = []
        except AgentOutputError as e:
            record["ok"] = False
            record["problems"] = [f"AgentOutputError: {e}"]
        except Exception as e:
            record["ok"] = False
            record["problems"] = [f"{type(e).__name__}: {e}"]
        results["interpret"].append(record)
        total_n += 1
        total_ok += int(record["ok"])
        mark = "✓" if record["ok"] else "✗"
        print(f"  [{mark}] 입력 {idx} — {label}")
        for p in record["problems"]:
            print(f"        - {p}")

    # --- safety_agent.py ---
    print("\n[safety_agent.py] — 실제 SafetyAgent.run() 경로, 6문장 배치 1회")
    agent = SafetyAgent(ai)
    record = {}
    try:
        output = await agent.run(SAFETY_PAYLOAD)
        by_before = {r.before: r.after for r in output.rewritten}
        problems = []
        # 점수·등급 / 관계판정은 재작성이 아니라 삭제(after == "")여야 한다 (safety.md 규칙 4·8)
        must_delete = ["관계 온도 B등급이에요", "이 정도면 헤어지는 게 나을까 싶어요"]
        for text in must_delete:
            if by_before.get(text) != "":
                problems.append(f"삭제돼야 하는데 남아있음: {text!r} → {by_before.get(text)!r}")
        record = {
            "ok": len(problems) == 0,
            "output": output.model_dump(mode="json"),
            "problems": problems,
        }
    except AgentOutputError as e:
        record = {"ok": False, "problems": [f"AgentOutputError: {e}"]}
    except Exception as e:
        record = {"ok": False, "problems": [f"{type(e).__name__}: {e}"]}
    results["safety"].append(record)
    total_n += 1
    total_ok += int(record.get("ok", False))
    mark = "✓" if record.get("ok") else "✗"
    print(f"  [{mark}] safety 배치")
    for p in record.get("problems", []):
        print(f"        - {p}")

    print("=" * 70)
    print(f"전체: {total_ok}/{total_n} 통과")
    print("\n※ 여기서 통과했다는 건 response_format을 포함한 실제 에이전트 코드 경로가 실 watsonx로")
    print("   끝까지 동작한다는 뜻입니다. 문장이 자연스러운지는 raw 결과 파일을 사람이 봐야 합니다.")

    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
