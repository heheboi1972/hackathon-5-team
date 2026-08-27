# 역할: 3-6c(advice_request 고정 문구 → LLM 생성 전환) 실측 검증 — chat_answer_agent.py의
#       advice_request 경로를 **실제 에이전트 코드 그대로**(agent.run()) 실 watsonx로 호출해서
#       확인한다. 3-7_chat_agent_real_llm_test.py와 정확히 같은 패턴 — 그 스크립트는
#       "term_count/advice_request는 LLM을 아예 안 쓰는 경로"라고 명시하며 advice_request를
#       대상에서 뺐었는데, 이제는 advice_request도 LLM을 쓰므로 이 스크립트로 별도 확인한다.
#
#       확인하려는 것 3가지:
#       ① 질문마다 실제로 다른 문구가 나오는가 (고정 문구 시절과 달리)
#       ② banned_patterns.txt 안전장치가 얼마나 자주 걸리는가 (너무 자주 걸리면 LLM 연결의
#          체감 효과가 별로 없다는 뜻)
#       ③ 안전장치를 통과한 문장들이 실제로 조언처럼 안 들리는지 — 이건 숫자로는 안 나오니
#          출력된 문장을 사람이 직접 읽고 판단해야 함
#
#       Docker 없이, FastAPI 서버 없이, Postgres/Qdrant 없이 돌아간다.
#
# 사용법 (레포 루트에서, 본인 PC 터미널 — venv 활성화 후, Docker/서버 켤 필요 없음):
#   python scripts/3-6c_advice_agent_real_llm_test.py
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
RESULT_PATH = Path(__file__).resolve().parent / "3-6c_advice_agent_real_llm_raw.json"

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


# advice_request 케이스 8개 — 실제로 사용자가 쓸 법한 다양한 표현. 2건(3, 4)은 윤아가 실사용
# 중 실제로 물어봤던 질문 그대로(⑰ 참고). 나머지는 서로 다른 표현 방식(직접 조언 요청/이별
# 뉘앙스/관계 판정 뉘앙스/궁합 질문)으로 골고루 섞음.
CASES = [
    (1, "우리 어떻게 화해해야 할까?"),
    (2, "이 정도면 헤어지는 게 나을까?"),
    (3, "요즘 연락이 좀 뜸한데 어떻게 하면 좋을까?"),  # 윤아 실사용 질문
    (4, "서로 서운한 게 쌓이지 않으려면 어떻게 해야 할까?"),  # 윤아 실사용 질문
    (5, "여자친구가 삐지면 어떻게 해야 돼?"),
    (6, "우리 궁합 잘 맞는 편이야?"),
    (7, "화해하려면 뭐부터 해야 돼?"),
    (8, "이 정도면 그만 만나는 게 맞는 걸까?"),
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
    from app.agents.chat_answer_agent import (
        ADVICE_FALLBACK_TEXT,
        ChatAnswerAgent,
        _ADVICE_BANNED_PATTERNS,
        _RESPONSE_FORMAT,
    )
    from app.models.report import ChatAnswerOutput
    from app.services.ai_service import WatsonxAIService

    ai = WatsonxAIService(
        api_key=api_key, url=url, project_id=project_id, model_id=model_id,
        embedding_model_id=embedding_model_id, reasoning_effort=reasoning_effort,
    )
    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort} | provider: {ai.provider_name}")
    print("=" * 70)

    agent = ChatAnswerAgent(ai)
    results: list[dict] = []
    fallback_count = 0

    for idx, message in CASES:
        payload = {"message": message, "history": []}
        record: dict = {"index": idx, "message": message}

        # ① 실제 프로덕션 경로 그대로 — 여기 나오는 게 진짜 사용자에게 나가는 값
        #    (chat_supervisor._advice()가 output.answer를 그대로 ChatResponse.redirect로 옮김)
        try:
            final = await agent.run("advice_request", payload)
            record["final_answer"] = final.answer
            record["fell_back"] = final.answer == ADVICE_FALLBACK_TEXT
        except AgentOutputError as e:
            record["final_answer"] = None
            record["error"] = f"AgentOutputError: {e}"
        except Exception as e:
            record["final_answer"] = None
            record["error"] = f"{type(e).__name__}: {e}"

        # ② 안전장치를 거치기 전 LLM 원문도 별도로 한 번 더 불러서 같이 보여준다 — 폴백이
        #    걸렸을 때 "원래 뭐라고 하려고 했는지", 안 걸렸을 때 "그대로 나간 문장이 맞는지"를
        #    한눈에 비교하기 위함. 매번 2번 호출하는 거라 이 스크립트 실행 비용은 좀 더 든다.
        try:
            raw = await agent.generate_validated(
                payload, ChatAnswerOutput, mock_key="chat_answer_advice_request",
                response_format=_RESPONSE_FORMAT,
            )
            record["raw_answer"] = raw.answer
            matched = [p.pattern for p in _ADVICE_BANNED_PATTERNS if p.search(raw.answer)]
            record["banned_pattern_hit"] = matched or None
        except Exception as e:
            record["raw_answer"] = None
            record["raw_error"] = f"{type(e).__name__}: {e}"

        if record.get("fell_back"):
            fallback_count += 1

        results.append(record)

        print(f"\n[{idx}] 질문: {message}")
        print(f"    LLM 원문 : {record.get('raw_answer')!r}")
        if record.get("banned_pattern_hit"):
            print(f"    → banned_patterns 매치: {record['banned_pattern_hit']}")
        mark = "폴백됨" if record.get("fell_back") else "그대로 사용"
        print(f"    최종 답변({mark}): {record.get('final_answer')!r}")
        if record.get("error"):
            print(f"    ⚠️ {record['error']}")

    print("\n" + "=" * 70)
    print(f"전체 {len(CASES)}건 중 폴백(고정 문구로 대체)된 건: {fallback_count}건")
    print(f"LLM 문구가 그대로 나간 건: {len(CASES) - fallback_count}건")
    print("\n※ 이 숫자와 위 문장들을 직접 읽고 판단할 것:")
    print("  - 폴백이 너무 잦으면(예: 8건 중 5건 이상) banned_patterns.txt가 너무 넓게 잡혀")
    print("    있다는 뜻일 수 있어요 — 어떤 규칙이 걸렸는지(banned_pattern_hit)를 보고 특정")
    print("    규칙이 자연스러운 공감 표현까지 과하게 막고 있다면 chat_answer.md 쪽 지시문을")
    print("    더 다듬거나(우선), 그래도 안 되면 banned_patterns.txt 해당 규칙을 조정하는 것도")
    print("    (신중하게, 다른 카드들도 같이 쓰는 규칙이라 영향 범위 큼) 고려할 수 있습니다.")
    print("  - '그대로 사용'된 문장들이 실제로 조언/판단처럼 안 들리는지 눈으로 확인하세요.")

    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
