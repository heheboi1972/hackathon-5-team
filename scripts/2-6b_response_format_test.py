# 역할: 형준님 제안 검증 — watsonx의 response_format(json_schema)이 interpret_agent의
#       evidence/sources를 "항상 객체(object) 형태"로 강제할 수 있는지 실측 확인.
#       (참조: prompts/interpret.md 알려진 한계 — 프롬프트만으로는 10개 중 1개꼴로 evidence/sources가
#        문자열로 축약되는 문제가 재현됨. response_format으로 API 레벨에서 형태를 못박을 수 있는지 테스트)
#
# 사용법 (레포 루트에서):
#   pip install ibm-watsonx-ai --break-system-packages   (이미 설치돼 있으면 생략, 1.4.0 이상 필요)
#   python scripts/2-6b_response_format_test.py
#
# 준비물: 레포 루트의 .env 에 AI_PROVIDER=watsonx, WATSONX_API_KEY / WATSONX_PROJECT_ID 채워져 있어야 함.
#         (docker나 postgres/qdrant는 필요 없음 — 순수 chat API 호출만 함)
#
# 테스트 입력 10개는 1-V4 때 쓴 것과 동일 (scripts/1-v4_interpret_prompt_test_kit.md) —
# 특히 입력 10번은 프롬프트만으로는 재테스트에서도 계속 문자열로 축약됐던 케이스라,
# response_format이 이 케이스를 실제로 고치는지가 이번 테스트의 핵심 확인 포인트.
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows cp949 콘솔에서도 한글 깨짐 방지
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
RESULT_PATH = Path(__file__).resolve().parent / "2-6b_response_format_raw.json"


def load_env(path: Path) -> dict[str, str]:
    """.env 를 아주 단순하게 파싱 (python-dotenv 의존성 없이)."""
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


# ---------------------------------------------------------------- 시스템 프롬프트 (interpret.md 최종본 그대로)

SYSTEM_PROMPT = """너는 커플의 카톡 대화 데이터를 오래 지켜본 다정한 친구야. 아래 규칙을 지키면서
입력으로 주어진 지표 변화 하나를 자연스러운 한국어로 해석해줘.

[입력]
metric: 어떤 지표인지 (예: question_rate)
direction: up 또는 down
magnitude: slight(조금) 또는 clear(눈에 띄게)
knowledge: 참고할 수 있는 지식 문서 후보 목록
evidence_candidates: 근거로 쓸 수 있는 실제 대화 스니펫 후보 목록

[출력 형식 — 반드시 JSON]
{
  "highlights": [
    {
      "observation": "관찰 한 문장",
      "interpretations": ["해석 절1", "해석 절2"],
      "evidence": [ evidence_candidates 중에서 고른 항목 (객체 그대로) ],
      "sources": [ knowledge 중에서 고른 항목 (객체 그대로) ]
    }
  ]
}

[규칙 — 반드시 지킬 것]
1. observation은 관찰 한 문장. 주어는 항상 "우리"이거나 생략. 특정 인물(A/B)을 지칭하지 않는다.
2. interpretations는 반드시 2개 이상. 각 항목은 종결어미 없이 끝나는 절이어야 한다.
   예: "바쁜 시기였을 수도" (O) / "바쁜 시기였을 수 있어요." (X, 종결어미 있음 - 금지)
   원인을 하나로 단정하지 말고, 가능성 있는 이유 여러 개를 제시하는 것이 목적이다.
3. 숫자를 절대 쓰지 않는다. 입력에 실제 숫자가 없으므로, 숫자를 쓴다면 지어낸 것이다.
   정도는 magnitude를 말로 표현한다 (slight → "조금", clear → "눈에 띄게").
4. 두 사람을 비교하는 표현을 쓰지 않는다. "더 ~하다", "~보다", "누가 더" 금지.
   단, 지난 기간과의 비교("지난 4주에 비해")는 사람 비교가 아니므로 허용한다.
5. evidence는 evidence_candidates 안에 있는 항목만, sources는 knowledge 안에 있는 항목만 고른다.
   후보가 비어 있으면 evidence 또는 sources를 빈 배열로 둔다. 절대 새로 지어내지 않는다.
   evidence와 sources는 항상 후보에 있는 객체(object) 형태 그대로 넣는다.
6. 톤은 판정하는 관찰자가 아니라, 이 관계를 오래 지켜본 다정한 친구처럼 따뜻하게.
   단정적이거나 평가하는 말투("문제가 있다", "안 좋다")는 피한다.

JSON 외의 다른 텍스트(설명, 인사말)는 출력하지 않는다."""

# ---------------------------------------------------------------- response_format (핵심 — 이번 테스트의 목적)
# interpret.md/API_SPEC의 evidence={session_id,at,snippet} / sources={doc,section} 객체 형태를
# API 호출 단계에서 스키마로 못박는다. strict=True면 vLLM 계열 백엔드에서 grammar 단위로 강제되는 것으로
# 알려져 있음(형준님 리서치) — gpt-oss가 복잡한 스키마를 거부하는 사례도 보고돼 있어 실측 필요.
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "interpret_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "highlights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "observation": {"type": "string"},
                            "interpretations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                            },
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "session_id": {"type": "integer"},
                                        "at": {"type": "string"},
                                        "snippet": {"type": "string"},
                                    },
                                    "required": ["session_id", "at", "snippet"],
                                    "additionalProperties": False,
                                },
                            },
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "doc": {"type": "string"},
                                        "section": {"type": "string"},
                                    },
                                    "required": ["doc", "section"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["observation", "interpretations", "evidence", "sources"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["highlights"],
            "additionalProperties": False,
        },
    },
}

# ---------------------------------------------------------------- 테스트 입력 10개 (1-V4와 동일, scripts/1-v4_interpret_prompt_test_kit.md)

TEST_INPUTS: list[tuple[int, str, dict]] = [
    (1, "질문 빈도 감소 (약하게)", {
        "metric": "question_rate", "direction": "down", "magnitude": "slight",
        "knowledge": [{"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"}],
        "evidence_candidates": [{"session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?"}],
    }),
    (2, "질문 빈도 증가 (눈에 띄게)", {
        "metric": "question_rate", "direction": "up", "magnitude": "clear",
        "knowledge": [{"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"}],
        "evidence_candidates": [{"session_id": 1150, "at": "2026-08-10T20:12:00+09:00", "snippet": "너 요즘 취미 뭐야?"}],
    }),
    (3, "메시지 길이 감소 (눈에 띄게)", {
        "metric": "message_length_median", "direction": "down", "magnitude": "clear",
        "knowledge": [{"doc": "communication_basics.md", "section": "짧은 답장의 의미"}],
        "evidence_candidates": [{"session_id": 1201, "at": "2026-08-15T22:30:00+09:00", "snippet": "ㅇㅇ"}],
    }),
    (4, "메시지 길이 증가 (약하게) — 근거·지식 후보 둘 다 없음", {
        "metric": "message_length_median", "direction": "up", "magnitude": "slight",
        "knowledge": [], "evidence_candidates": [],
    }),
    (5, "답장 간격 증가 (눈에 띄게) — 비교 유혹 큰 케이스", {
        "metric": "reply_gap_median_min", "direction": "up", "magnitude": "clear",
        "knowledge": [{"doc": "communication_basics.md", "section": "응답 속도와 상황"}],
        "evidence_candidates": [{"session_id": 1187, "at": "2026-08-19T23:41:00+09:00", "snippet": "미안 지금 봤어"}],
    }),
    (6, "답장 간격 감소 (약하게)", {
        "metric": "reply_gap_median_min", "direction": "down", "magnitude": "slight",
        "knowledge": [{"doc": "communication_basics.md", "section": "응답 속도와 상황"}],
        "evidence_candidates": [{"session_id": 1210, "at": "2026-08-21T13:05:00+09:00", "snippet": "ㅋㅋ바로답장"}],
    }),
    (7, "대화 재개 지연 증가 (눈에 띄게)", {
        "metric": "resume_delay_median_min", "direction": "up", "magnitude": "clear",
        "knowledge": [{"doc": "communication_basics.md", "section": "대화 공백의 의미"}],
        "evidence_candidates": [{"session_id": 1230, "at": "2026-08-18T09:15:00+09:00", "snippet": "다시 왔어"}],
    }),
    (8, "대화 재개 지연 감소 (약하게) — 지식 후보 없음", {
        "metric": "resume_delay_median_min", "direction": "down", "magnitude": "slight",
        "knowledge": [], "evidence_candidates": [{"session_id": 1245, "at": "2026-08-22T19:00:00+09:00", "snippet": "바로 답장왔네"}],
    }),
    (9, "질문 빈도 감소 — 근거·지식 후보 여러 개", {
        "metric": "question_rate", "direction": "down", "magnitude": "clear",
        "knowledge": [
            {"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"},
            {"doc": "conflict_patterns.md", "section": "회피형 대화"},
        ],
        "evidence_candidates": [
            {"session_id": 1301, "at": "2026-08-05T21:00:00+09:00", "snippet": "그냥 그랬어"},
            {"session_id": 1302, "at": "2026-08-06T22:10:00+09:00", "snippet": "몰라 피곤해"},
        ],
    }),
    (10, "메시지 길이 감소 — 1차·2차 테스트 모두에서 evidence/sources가 문자열로 축약됐던 케이스", {
        "metric": "message_length_median", "direction": "down", "magnitude": "clear",
        "knowledge": [{"doc": "communication_basics.md", "section": "짧은 답장의 의미"}],
        "evidence_candidates": [{"session_id": 1320, "at": "2026-08-20T23:50:00+09:00", "snippet": "응"}],
    }),
]


def validate(parsed: dict) -> tuple[bool, list[str]]:
    """evidence/sources가 항상 객체(dict)인지, 필수 필드가 다 있는지 확인. (json_schema 자체가 타입을 보장해도
    한 번 더 코드로 확인 — "정말 강제됐는지"를 직접 눈으로 검증하는 것이 이번 테스트의 목적)"""
    problems: list[str] = []
    highlights = parsed.get("highlights")
    if not isinstance(highlights, list) or not highlights:
        return False, ["highlights가 비어있거나 배열이 아님"]
    for i, h in enumerate(highlights):
        for key, required_fields in (("evidence", {"session_id", "at", "snippet"}), ("sources", {"doc", "section"})):
            items = h.get(key, [])
            if not isinstance(items, list):
                problems.append(f"highlights[{i}].{key} 가 배열이 아님: {items!r}")
                continue
            for j, item in enumerate(items):
                if not isinstance(item, dict):
                    problems.append(f"highlights[{i}].{key}[{j}] 가 객체가 아니고 {type(item).__name__}: {item!r}")
                elif not required_fields.issubset(item.keys()):
                    problems.append(f"highlights[{i}].{key}[{j}] 에 필수 필드 누락: {item!r}")
        interpretations = h.get("interpretations", [])
        if not isinstance(interpretations, list) or len(interpretations) < 2:
            problems.append(f"highlights[{i}].interpretations 가 2개 미만: {interpretations!r}")
    return (len(problems) == 0), problems


def main() -> None:
    env = load_env(ENV_PATH)
    api_key = env.get("WATSONX_API_KEY", "")
    project_id = env.get("WATSONX_PROJECT_ID", "")
    url = env.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model_id = env.get("WATSONX_MODEL_ID", "openai/gpt-oss-120b")
    reasoning_effort = env.get("WATSONX_REASONING_EFFORT", "low")

    if not api_key or not project_id:
        print("[에러] .env 에 WATSONX_API_KEY / WATSONX_PROJECT_ID 가 없습니다. AI_PROVIDER=watsonx로 설정하고 채워주세요.")
        sys.exit(1)

    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference

    creds = Credentials(url=url, api_key=api_key)
    model = ModelInference(model_id=model_id, credentials=creds, project_id=project_id)

    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort} | response_format: json_schema(strict=True)")
    print("=" * 70)

    results = []
    ok_count = 0
    for idx, label, payload in TEST_INPUTS:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        record: dict = {"index": idx, "label": label, "input": payload}
        try:
            resp = model.chat(
                messages=messages,
                params={
                    "temperature": 0,
                    "max_tokens": 2000,
                    "reasoning_effort": reasoning_effort,
                    "response_format": RESPONSE_FORMAT,
                },
            )
            msg = resp["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            record["raw_content"] = content
            record["finish_reason"] = resp["choices"][0].get("finish_reason")
            if not content:
                record["ok"] = False
                record["problems"] = ["본문이 비어있음 (토큰 부족 또는 reasoning만 나옴 — max_tokens 늘려서 재시도 필요)"]
            else:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    record["ok"] = False
                    record["problems"] = [f"JSON 파싱 실패: {e}"]
                else:
                    ok, problems = validate(parsed)
                    record["ok"] = ok
                    record["problems"] = problems
                    record["parsed"] = parsed
        except Exception as e:
            # response_format 자체가 이 SDK 버전/모델에서 거부되면 여기서 잡힘 — 이것도 중요한 결과라 기록
            record["ok"] = False
            record["problems"] = [f"API 호출 자체가 실패함 (response_format이 이 모델에서 안 먹힐 수 있음): {type(e).__name__}: {e}"]

        results.append(record)
        mark = "✓" if record["ok"] else "✗"
        if record["ok"]:
            ok_count += 1
        print(f"[{mark}] 입력 {idx} — {label}")
        if not record["ok"]:
            for p in record["problems"]:
                print(f"       - {p}")

    print("=" * 70)
    print(f"결과: {ok_count}/{len(TEST_INPUTS)} 통과 (evidence/sources가 항상 객체로 나옴)")
    if ok_count == len(TEST_INPUTS):
        print("→ response_format으로 10/10 전부 객체 형태 보장됨. 다만 이건 이 10개 케이스에서만 확인된 것 —")
        print("  코드 쪽 방어 로직(evidence/sources 재매칭)은 그래도 이중 안전장치로 남겨두는 걸 권장.")
    else:
        print("→ response_format을 써도 100% 보장은 아닌 것으로 보임. 실패한 케이스의 problems 내용을 보고")
        print("  strict 옵션이나 스키마 자체를 더 손봐야 할 수도 있음. (코드 방어 로직은 필수로 유지)")

    RESULT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
