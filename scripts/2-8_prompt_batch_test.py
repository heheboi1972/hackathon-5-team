# 역할: Day2 "다음 할일" — 실제로 LLM을 호출하는 프롬프트 3개(safety.md / chat_intent.md /
#       chat_answer.md)를 골든셋 입력으로 한 번씩 돌려서, 프롬프트 문구가 아니라 실측으로
#       계약(불변 규칙)을 지키는지 확인한다.
#
#       ⚠️ select.md / suggest.md 는 이 스크립트에 없음 — 이유는 파일 하단 "제외 사유" 참고
#          (요약: select_agent.py/suggest_agent.py가 이미 결정론적 코드로 확정되어 있어서
#          운영 코드가 이 두 프롬프트를 애초에 호출하지 않음. 실측 대상이 아님.)
#
# 사용법 (레포 루트에서):
#   python scripts/2-8_prompt_batch_test.py
#   (.env 에 AI_PROVIDER=watsonx, WATSONX_API_KEY / WATSONX_PROJECT_ID 필요 — 2-6b와 동일)
#
# 이 스크립트가 하는 일:
#   1) api/app/prompts/{safety,chat_intent,chat_answer}.md 를 "있는 그대로" system prompt로 사용
#      (AgentBase.prompt()가 실제로 이렇게 파일 통째로 읽어서 쓰는 것과 동일한 방식 — 2026-08-25 확인)
#   2) 골든셋 입력을 하나씩(safety는 배치 1번) 호출
#   3) 사람이 다 읽지 않아도 되게, 계약 위반 여부를 코드로 최대한 기계적으로 체크
#      (표현이 자연스러운지 같은 "느낌"은 사람이 raw output을 봐야 함 — 그래서 결과를 파일로도 저장)
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
PROMPTS_DIR = REPO_ROOT / "api" / "app" / "prompts"
RESULT_PATH = Path(__file__).resolve().parent / "2-8_prompt_batch_raw.json"


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


def strip_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)


# ---------------------------------------------------------------- safety.md
# 실제 safety_agent.py의 호출부(2026-08-25 확인)와 동일한 입력 키를 그대로 사용:
#   generate_validated({"sentences": flagged}, SafetyOutput, mock_key="safety")
# 배치 1번으로 아래 6문장을 동시에 넣는다 (실제 코드도 flagged 문장을 한 번에 배치로 보냄).

SAFETY_INPUT = {
    "sentences": [
        "A가 질문을 많이 했어요",
        "B보다 A가 더 자주 답장했어요",
        "질문이 30% 늘었어요",
        "관계 온도 B등급이에요",
        "더 자주 연락하세요",
        "이 정도면 헤어지는 게 나을까 싶어요",
    ]
}

# (문장, 카테고리, 기대동작) — must_delete=True면 after=="" 이어야 함
SAFETY_EXPECT = [
    ("A가 질문을 많이 했어요", "인물 지목", False),
    ("B보다 A가 더 자주 답장했어요", "두 사람 비교", False),
    ("질문이 30% 늘었어요", "수치", False),
    ("관계 온도 B등급이에요", "점수·등급", True),
    ("더 자주 연락하세요", "명령·당위", False),
    ("이 정도면 헤어지는 게 나을까 싶어요", "관계 판정", True),
]


def validate_safety(parsed: dict) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if not isinstance(parsed.get("passed"), bool):
        problems.append("passed가 bool이 아님")
    rewritten = parsed.get("rewritten")
    if not isinstance(rewritten, list):
        return False, ["rewritten이 배열이 아님"]
    by_before = {r.get("before"): r.get("after", "") for r in rewritten if isinstance(r, dict)}
    for before, category, must_delete in SAFETY_EXPECT:
        if before not in by_before:
            problems.append(f"[{category}] 입력 문장이 결과에 없음: {before!r}")
            continue
        after = by_before[before]
        if must_delete:
            if after != "":
                problems.append(f"[{category}] 삭제돼야 하는데 남아있음: {after!r}")
            continue
        if after == "" or after == before:
            problems.append(f"[{category}] 재작성이 안 됨(비어있거나 원문 그대로): {after!r}")
            continue
        if re.search(r"\b[AB]\s*(?:가|이|는|은|의|님|씨)\b", after):
            problems.append(f"[{category}] 재작성 후에도 A/B 인물 지칭 남음: {after!r}")
        if re.search(r"\d+\s*(?:%|퍼센트)", after):
            problems.append(f"[{category}] 재작성 후에도 숫자·퍼센트 남음: {after!r}")
        if re.search(r"(하세요|해야\s*(?:해|합니다|해요)|하셔야)", after):
            problems.append(f"[{category}] 재작성 후에도 명령·당위 표현 남음: {after!r}")
    return len(problems) == 0, problems


# ---------------------------------------------------------------- chat_intent.md
# 입력: {message, focus_range?, history?} — API_SPEC §6.1 / models/api.py ChatRequest 기준

CHAT_INTENT_CASES = [
    ("우리 언제 처음 자기야라고 불렀지?", {}, "fact_query"),
    ("요즘 우리 질문 많이 해?", {}, "metric_query"),
    ("지난주 리포트 요약해줘", {}, "report_query"),
    ("우리 어떻게 화해해야 할까?", {}, "advice_request"),
    ("오늘 날씨 어때?", {}, "other"),
    ("우리 대화 패턴 보고 조언해줘", {}, "advice_request"),  # 경계 규칙: 혼합 시 advice_request 우선
    ("이 기간 질문 얼마나 했어?", {"focus_range": {"start": "2026-08-01", "end": "2026-08-07"}}, "metric_query"),  # focus_range 있어도 fact_query 아님
    ("고마워", {}, "other"),
]

VALID_INTENTS = {"fact_query", "metric_query", "report_query", "advice_request", "other"}


def validate_chat_intent(parsed: dict, expect: str) -> tuple[bool, list[str]]:
    intent = parsed.get("intent")
    problems = []
    if intent not in VALID_INTENTS:
        problems.append(f"허용되지 않은 intent 값: {intent!r} (term_count가 나오면 안 됨 — 이건 항상 금지)")
    elif intent != expect:
        problems.append(f"기대: {expect!r} / 실제: {intent!r}")
    return len(problems) == 0, problems


# ---------------------------------------------------------------- chat_answer.md
# 입력: 원 메시지 + intent별 tool 결과 (API_SPEC §8 시그니처 기준, 3개 툴 모두 TODO(윤석) — provisional)
# metric_query는 2026-08-25 결정(ISSUE A7)으로 get_metrics 입력이 {range, baseline, comment}
# (돌아보기 화면과 동일한 타입)로 바뀜 — answer 문장엔 숫자 절대 금지, 숫자는 metrics 필드로만.

CHAT_ANSWER_CASES = [
    (
        "fact_query 정답 있음",
        {
            "message": "우리 언제 처음 자기야라고 불렀지?",
            "intent": "fact_query",
            "search_results": [
                {"session_id": 812, "at": "2026-03-14T19:22:00+09:00", "sender": "a", "snippet": "자기야 뭐해", "score": 0.91},
                {"session_id": 55, "at": "2026-01-02T10:00:00+09:00", "sender": "b", "snippet": "오늘 날씨 좋다", "score": 0.12},
            ],
        },
        {"must_have_citations": True, "must_contain_any": ["자기야"], "metrics_null": True},
    ),
    (
        "fact_query 정답 없음",
        {
            "message": "우리 제주도 언제 갔었지?",
            "intent": "fact_query",
            "search_results": [
                {"session_id": 90, "at": "2026-02-01T10:00:00+09:00", "sender": "a", "snippet": "밥 먹었어?", "score": 0.08},
            ],
        },
        {"must_have_citations": False, "must_contain_any": ["찾지 못했"], "metrics_null": True},
    ),
    (
        "metric_query 답장 느려짐 (comment 재사용)",
        {
            "message": "요즘 답장 느려졌어?",
            "intent": "metric_query",
            "metrics": {
                "range": {"question_rate": {"couple": 0.2, "mine": 0.1}, "reply_gap_median_min": {"couple": 12, "mine": 3}, "message_count": 187},
                "baseline": {"weeks": 8, "question_rate": {"couple": 0.23, "mine": 0.22}, "reply_gap_median_min": {"couple": 5, "mine": 4}, "message_count": 210},
                "comment": "지난 8주보다 답장이 많이 느려졌어요",
            },
        },
        {"must_have_citations": False, "must_have_metrics": True, "no_digits_except_weeks": True},
    ),
    (
        "metric_query 정확한 수치 요청 (그래도 문장엔 숫자 금지)",
        {
            "message": "정확히 몇 프로야?",
            "intent": "metric_query",
            "metrics": {
                "range": {"question_rate": {"couple": 0.2, "mine": 0.1}, "reply_gap_median_min": {"couple": 12, "mine": 3}, "message_count": 187},
                "baseline": {"weeks": 8, "question_rate": {"couple": 0.23, "mine": 0.22}, "reply_gap_median_min": {"couple": 5, "mine": 4}, "message_count": 210},
                "comment": "지난 8주보다 답장이 많이 느려졌어요",
            },
        },
        {"must_have_citations": False, "must_have_metrics": True, "no_digits_except_weeks": True, "must_contain_any": ["카드", "위에"]},
    ),
    (
        "report_query 준비 안 됨",
        {
            "message": "이번 주 리포트 뭐라고 나왔어?",
            "intent": "report_query",
            "report": {"status": "pending", "week_start": "2026-08-24"},
        },
        {"must_have_citations": False, "must_contain_any": ["준비"], "metrics_null": True},
    ),
    (
        "report_query 정상",
        {
            "message": "저번주 리포트에서 뭐라고 했었지?",
            "intent": "report_query",
            "report": {
                "week_start": "2026-08-17",
                "summary": "이번 주 대화가 안정적이었어요",
                "highlights": [{"observation": "요즘 대화가 짧게 끝나는 편이에요", "interpretations": ["바쁜 시기였을 수도"]}],
                "suggestions": [{"text": "서로 안부를 물어보면 어떨까요"}],
            },
        },
        {"must_have_citations": False, "must_contain_any": ["짧게", "안부"], "metrics_null": True},
    ),
]


def validate_chat_answer(parsed: dict, expect: dict) -> tuple[bool, list[str]]:
    problems = []
    answer = parsed.get("answer", "")
    citations = parsed.get("citations")
    metrics = parsed.get("metrics")
    if not isinstance(answer, str) or not answer.strip():
        problems.append("answer가 비어있거나 문자열이 아님")
    if not isinstance(citations, list):
        problems.append("citations가 배열이 아님")
        citations = []
    if expect.get("must_have_citations") and not citations:
        problems.append("citations가 비어있으면 안 되는 케이스인데 비어있음")
    if not expect.get("must_have_citations") and citations:
        problems.append(f"citations가 비어있어야 하는데 값이 있음(P-4 대상 아닌 intent): {citations!r}")
    if expect.get("metrics_null") and metrics is not None:
        problems.append(f"metrics가 null이어야 하는 intent인데 값이 있음: {metrics!r}")
    if expect.get("must_have_metrics"):
        if not isinstance(metrics, dict) or not {"range", "baseline", "comment"}.issubset(metrics.keys()):
            problems.append(f"metrics가 {{range, baseline, comment}} 형태로 채워져야 하는데 아님: {metrics!r}")
    if expect.get("no_digits_except_weeks") and isinstance(answer, str):
        stripped = re.sub(r"\d+주", "", answer)
        if any(ch.isdigit() for ch in stripped):
            problems.append(f"answer 문장에 숫자가 남아있음(metric_query는 숫자 금지 — 2026-08-25 결정, ISSUE A7): {answer!r}")
    for key in ("must_contain_any", "must_contain_any_2"):
        needles = expect.get(key)
        if needles and not any(n in answer for n in needles):
            problems.append(f"answer에 {needles} 중 하나도 없음: {answer!r}")
    for needle in expect.get("forbid_any", []):
        if needle in answer:
            problems.append(f"answer에 있으면 안 되는 표현 있음: {needle!r} in {answer!r}")
    return len(problems) == 0, problems


# ---------------------------------------------------------------- 실행

def main() -> None:
    env = load_env(ENV_PATH)
    api_key = env.get("WATSONX_API_KEY", "")
    project_id = env.get("WATSONX_PROJECT_ID", "")
    url = env.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model_id = env.get("WATSONX_MODEL_ID", "openai/gpt-oss-120b")
    reasoning_effort = env.get("WATSONX_REASONING_EFFORT", "low")

    if not api_key or not project_id:
        print("[에러] .env 에 WATSONX_API_KEY / WATSONX_PROJECT_ID 가 없습니다.")
        sys.exit(1)

    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference

    creds = Credentials(url=url, api_key=api_key)
    model = ModelInference(model_id=model_id, credentials=creds, project_id=project_id)

    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort}")
    print("=" * 70)

    all_results: dict[str, list[dict]] = {}
    total_ok = 0
    total_n = 0

    def call(system_prompt: str, payload: dict) -> tuple[str | None, dict | None, list[str]]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            resp = model.chat(
                messages=messages,
                params={"temperature": 0, "max_tokens": 1500, "reasoning_effort": reasoning_effort},
            )
            msg = resp["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                return None, None, ["본문이 비어있음 (토큰 부족/reasoning만 나옴)"]
            try:
                parsed = json.loads(strip_fences(content))
            except json.JSONDecodeError as e:
                return content, None, [f"JSON 파싱 실패: {e}"]
            return content, parsed, []
        except Exception as e:
            return None, None, [f"API 호출 실패: {type(e).__name__}: {e}"]

    # --- safety.md (배치 1콜) ---
    print("\n[safety.md] — 6문장 배치 1회 호출")
    safety_prompt = (PROMPTS_DIR / "safety.md").read_text(encoding="utf-8")
    raw, parsed, problems = call(safety_prompt, SAFETY_INPUT)
    records = []
    if parsed is not None and not problems:
        ok, problems = validate_safety(parsed)
    else:
        ok = False
    record = {"raw": raw, "parsed": parsed, "ok": ok, "problems": problems}
    records.append(record)
    all_results["safety"] = records
    total_n += 1
    total_ok += int(ok)
    print(f"  [{'✓' if ok else '✗'}] safety 배치")
    for p in problems:
        print(f"        - {p}")

    # --- chat_intent.md ---
    print("\n[chat_intent.md] — 8개 케이스")
    chat_intent_prompt = (PROMPTS_DIR / "chat_intent.md").read_text(encoding="utf-8")
    records = []
    for message, extra, expect in CHAT_INTENT_CASES:
        payload = {"message": message, **extra}
        raw, parsed, problems = call(chat_intent_prompt, payload)
        if parsed is not None and not problems:
            ok, problems = validate_chat_intent(parsed, expect)
        else:
            ok = False
        records.append({"label": message, "input": payload, "raw": raw, "parsed": parsed, "ok": ok, "problems": problems})
        total_n += 1
        total_ok += int(ok)
        print(f"  [{'✓' if ok else '✗'}] {message!r} (기대: {expect})")
        for p in problems:
            print(f"        - {p}")
    all_results["chat_intent"] = records

    # --- chat_answer.md ---
    print("\n[chat_answer.md] — 6개 케이스")
    chat_answer_prompt = (PROMPTS_DIR / "chat_answer.md").read_text(encoding="utf-8")
    records = []
    for label, payload, expect in CHAT_ANSWER_CASES:
        raw, parsed, problems = call(chat_answer_prompt, payload)
        if parsed is not None and not problems:
            ok, problems = validate_chat_answer(parsed, expect)
        else:
            ok = False
        records.append({"label": label, "input": payload, "raw": raw, "parsed": parsed, "ok": ok, "problems": problems})
        total_n += 1
        total_ok += int(ok)
        print(f"  [{'✓' if ok else '✗'}] {label}")
        for p in problems:
            print(f"        - {p}")
    all_results["chat_answer"] = records

    print("=" * 70)
    print(f"전체: {total_ok}/{total_n} 통과")
    print("\n※ 기계적으로 체크한 건 '계약 위반'(citations 규칙, 금지 표현, intent 값) 뿐입니다.")
    print("   문장이 자연스러운지·톤이 맞는지는 아래 raw 결과 파일을 사람이 눈으로 봐야 합니다.")

    RESULT_PATH.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- select.md / suggest.md 제외 사유
# api/app/agents/select_agent.py, suggest_agent.py 코드를 직접 확인함(2026-08-25):
#   - SelectAgent.run()  → select_candidates() 순수 파이썬 함수만 호출. self.ai 사용 없음.
#     select.md 상단 "메모 (C1)" — "코드가 결정론으로 뽑으면 이 에이전트는 없어도 된다" — 가 이미
#     그렇게 결정되어 구현까지 끝난 상태 (docstring: "ISSUE C1 결정에 따라 실제 provider에서도
#     LLM을 호출하지 않는다").
#   - SuggestAgent.run() → 마찬가지로 LLM 호출 없이 템플릿을 정렬·필터링해서 그대로 반환.
#     docstring: "템플릿 선택은 결정론적이므로 provider와 무관하게 LLM을 호출하지 않는다."
# 즉 운영 코드가 이 두 프롬프트를 애초에 호출하지 않으므로, Prompt Lab에서 실측해도 실제 동작과
# 무관하다. select.md/suggest.md 파일 자체는 "참고 문서"로만 남아있는 상태로 보임 — 필요하면
# 윤석님께 이 두 파일을 삭제하거나 "미사용" 표시를 남길지 확인하는 게 좋을 듯.
