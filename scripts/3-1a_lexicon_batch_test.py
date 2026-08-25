# 역할: 3-1a "lexicon.md 100단어 배치 테스트" — 1-8에서 단어를 하나씩만 넣어 검증했던 것과
#       달리, 실제 서비스가 하는 대로 100단어를 한 배치에 넣었을 때도 아래가 그대로 되는지 확인:
#       (1) 철자 변형(조아/좋앙 등)이 같은 canonical로 묶이는지 — 1-8에서 "검증 못 함"으로
#           남겨뒀던 부분, 이번 테스트의 핵심 목적.
#       (2) 100개를 한 번에 넣어도 입력 단어가 하나도 안 빠지고 다 나오는지(배치 크기 때문에
#           잘리거나 누락되는 게 없는지).
#       (3) 호칭(exclude) 변형도 배치 안에서 계속 exclude로 유지되는지.
#       (4) canonical 표기 방식이 그룹마다 들쭉날쭉하지 않은지(1-8에서 발견한 낮은 우선순위 이슈).
#
# 이 스크립트는 build_lexicon 잡 코드(services/lexicon.py, 아직 미착수)를 통해서가 아니라,
# 2-8과 같은 방식으로 lexicon.md 파일 전체를 시스템 프롬프트로 그대로 써서 watsonx를 직접
# 호출합니다 — 잡 코드가 없어도 프롬프트 자체의 배치 처리 품질만 먼저 검증하기 위함입니다.
#
# 사용법 (레포 루트에서, 본인 PC 터미널 — venv 활성화 후):
#   python scripts/3-1a_lexicon_batch_test.py
#   (.env 에 WATSONX_API_KEY / WATSONX_PROJECT_ID 필요 — 2-6b/2-8과 동일)
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
PROMPT_PATH = REPO_ROOT / "api" / "app" / "prompts" / "lexicon.md"
RESULT_PATH = Path(__file__).resolve().parent / "3-1a_lexicon_batch_raw.json"


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


# ------------------------------------------------------------ 핵심: 철자 변형 그룹 (10개)
# 그룹당 canonical 기대값 + (변형 단어, 예시 3건) 목록. 예시는 lexicon.md 안의 원래 예시
# 톤(바보/자기야)을 그대로 재사용하고, 나머지 그룹은 같은 스타일로 새로 지음.
VARIANT_GROUPS: dict[str, dict] = {
    "좋아": {
        "expect_polarity": "pos",
        "words": {
            "좋아": ["이거 완전 좋아", "오늘 날씨 좋아", "그거 진짜 좋아"],
            "조아": ["나 이거 조아 ㅋㅋ", "완전 조아", "오늘 조아"],
            "좋앙": ["헤헤 좋앙", "완전 좋앙", "이거 좋앙"],
            "조아용": ["저는 조아용", "그거 조아용", "완전 조아용"],
        },
    },
    "짜증나": {
        "expect_polarity": "neg",
        "words": {
            "짜증나": ["오늘 진짜 짜증나", "그거 완전 짜증나", "일이 안 풀려서 짜증나"],
            "짱나": ["진짜 짱나 ㅡㅡ", "완전 짱나", "이거 짱나"],
            "징나": ["아 징나 진짜", "완전 징나", "그거 징나"],
            "쨩나": ["아오 쨩나", "완전 쨩나", "진짜 쨩나"],
        },
    },
    "사랑해": {
        "expect_polarity": "pos",
        "words": {
            "사랑해": ["많이 사랑해", "진짜 사랑해", "오늘도 사랑해"],
            "사랑행": ["완전 사랑행", "많이 사랑행", "오늘도 사랑행"],
            "사랑햄": ["진짜 사랑햄", "많이 사랑햄", "오늘도 사랑햄"],
            "사랑함": ["많이 사랑함", "진짜 사랑함", "오늘도 사랑함"],
        },
    },
    "보고싶어": {
        "expect_polarity": "pos",
        "words": {
            "보고싶어": ["오늘따라 보고싶어", "많이 보고싶어", "벌써 보고싶어"],
            "보고싶당": ["헤헤 보고싶당", "많이 보고싶당", "벌써 보고싶당"],
            "보고파": ["오늘따라 보고파", "많이 보고파", "벌써 보고파"],
            "보곺아": ["헤헤 보곺아", "많이 보곺아", "벌써 보곺아"],
        },
    },
    "서운해": {
        "expect_polarity": "neg",
        "words": {
            "서운해": ["그 말 듣고 서운해", "혼자 두고 가서 서운해", "조금 서운해"],
            "서운행": ["그래서 서운행", "조금 서운행", "많이 서운행"],
            "서운하다": ["그 말 듣고 서운하다", "조금 서운하다", "많이 서운하다"],
        },
    },
    "답답해": {
        "expect_polarity": "neg",
        "words": {
            "답답해": ["연락이 안 돼서 답답해", "말이 안 통해서 답답해", "진짜 답답해"],
            "답답행": ["그래서 답답행", "진짜 답답행", "완전 답답행"],
            "답답하다": ["연락이 안 돼서 답답하다", "말이 안 통해서 답답하다", "진짜 답답하다"],
        },
    },
    "미안해": {
        "expect_polarity": None,  # 사과 표현 — pos/neg 어느 쪽이든 강요하지 않고 canonical 그룹핑만 확인
        "words": {
            "미안해": ["늦어서 미안해", "연락 못해서 미안해", "진짜 미안해"],
            "미얀해": ["늦어서 미얀해", "진짜 미얀해", "많이 미얀해"],
            "미안행": ["늦어서 미안행", "진짜 미안행", "많이 미안행"],
            "미안하다": ["늦어서 미안하다", "연락 못해서 미안하다", "진짜 미안하다"],
        },
    },
    "고마워": {
        "expect_polarity": "pos",
        "words": {
            "고마워": ["챙겨줘서 고마워", "항상 고마워", "진짜 고마워"],
            "고마워용": ["챙겨줘서 고마워용", "항상 고마워용", "진짜 고마워용"],
            "고맙다": ["챙겨줘서 고맙다", "항상 고맙다", "진짜 고맙다"],
        },
    },
    # --- exclude 그룹: 호칭은 철자 변형이 있어도 계속 exclude여야 함 (1-8에서 취약했던 지점) ---
    "자기야": {
        "expect_polarity": "exclude",
        "words": {
            "자기야": ["자기야 뭐해", "자기야 사랑해", "자기야 이따 봐"],
            "자기얌": ["자기얌 뭐해", "자기얌 밥 먹었어", "자기얌 이따 봐"],
            "자기용": ["자기용 뭐해", "자기용 밥 먹었어", "자기용 이따 봐"],
        },
    },
    # --- 반어적 애정표현: 겉으론 부정 단어지만 pos여야 함 (1-8 골든셋과 동일 취지) ---
    "바보": {
        "expect_polarity": "pos",
        "words": {
            "바보": ["너 진짜 바보야 ㅋㅋ", "바보같이 왜 그랬어 귀엽게", "우리 바보 뭐해"],
            "바보야": ["너 완전 바보야", "바보야 귀엽게 왜그래", "우리 바보야 뭐해"],
            "바봉": ["너 진짜 바봉 ㅋㅋ", "바봉같이 왜그래 귀엽게", "우리 바봉 뭐해"],
            "바보임": ["너 완전 바보임 ㅋㅋ", "바보임 진짜 귀엽게", "우리 바보임 뭐해"],
        },
    },
}

# ------------------------------------------------------------ 배치 채우기용 단독 단어 (~58개)
# 실제 100단어 배치 규모를 흉내내기 위한 채움용. 문맥은 간단한 템플릿으로 생성(자연스러움보다
# "배치 규모에서도 안 빠지고/안 헷갈리고 나오는지"가 이번 테스트의 초점).
_POS_FILL = [
    "행복해", "좋았어", "설레", "즐거워", "재밌어", "웃겨", "최고야", "완벽해", "짱이야",
    "소중해", "애틋해", "든든해", "안심돼", "편안해", "신나", "뿌듯해", "감동이야", "다행이야",
    "존예", "존잘", "꿀잼", "고생했어", "수고했어", "응원해",
]
_NEG_FILL = [
    "힘들어", "화났어", "삐졌어", "질투나", "무서워", "지겨워", "심심해", "우울해", "불안해",
    "억울해", "걱정돼", "서럽다", "눈물나", "속상해", "아쉬워", "부럽다", "얄미워", "귀찮아",
    "지친다", "미워",
]
_NEUTRAL_FILL = ["알겠어", "그래", "오케이", "그렇구나", "궁금해"]
_EXCLUDE_NAME_FILL = ["민준아", "지훈아", "서연아"]
_EXCLUDE_NOUN_FILL = ["학교", "카페", "영화", "산책", "지하철", "버스"]
_EXCLUDE_ID_FILL = ["010-1234-5678", "1998년생"]
_EXCLUDE_SWEAR_FILL = ["시발", "개짜증"]


def _fill_examples(word: str, kind: str) -> list[str]:
    if kind == "pos":
        return [f"오늘 진짜 {word}", f"자기 덕분에 {word}", f"우리 같이 있어서 {word}"]
    if kind == "neg":
        return [f"오늘 진짜 {word}", f"그것 때문에 {word}", f"요즘 좀 {word}"]
    if kind == "neutral":
        return [f"응 {word}", f"어 {word}", f"{word} 알았어"]
    if kind == "name":
        return [f"{word} 뭐해", f"{word}이랑 얘기했어", f"{word} 얘기하는거 봤어"]
    if kind == "noun":
        return [f"{word} 갈까", f"{word} 다녀왔어", f"{word} 언제 가?"]
    if kind == "id":
        return [f"번호는 {word}야", f"{word} 맞지?", f"{word}로 연락해"]
    if kind == "swear":
        return [f"아 {word}", f"진짜 {word}", f"{word} 이거"]
    raise ValueError(kind)


def build_batch() -> tuple[list[dict], dict[str, dict]]:
    """반환: (watsonx에 보낼 payload 리스트, term -> 기대치 메타 딕셔너리)"""
    payload: list[dict] = []
    expect: dict[str, dict] = {}

    for canonical, spec in VARIANT_GROUPS.items():
        for word, examples in spec["words"].items():
            payload.append({"word": word, "examples": examples})
            expect[word] = {"group": canonical, "expect_polarity": spec["expect_polarity"]}

    fill_specs = (
        (_POS_FILL, "pos", "pos"),
        (_NEG_FILL, "neg", "neg"),
        (_NEUTRAL_FILL, "neutral", "neutral"),
        (_EXCLUDE_NAME_FILL, "name", "exclude"),
        (_EXCLUDE_NOUN_FILL, "noun", "exclude"),
        (_EXCLUDE_ID_FILL, "id", "exclude"),
        (_EXCLUDE_SWEAR_FILL, "swear", "exclude"),
    )
    for words, kind, expect_polarity in fill_specs:
        for word in words:
            payload.append({"word": word, "examples": _fill_examples(word, kind)})
            expect[word] = {"group": None, "expect_polarity": expect_polarity}

    return payload, expect


def validate(parsed: list, expect: dict[str, dict]) -> tuple[bool, list[str], dict]:
    problems: list[str] = []
    if not isinstance(parsed, list):
        return False, ["출력이 배열이 아님"], {}

    by_term: dict[str, dict] = {}
    for item in parsed:
        if not isinstance(item, dict) or "term" not in item:
            problems.append(f"형식이 이상한 항목: {item!r}")
            continue
        by_term[item["term"]] = item

    # (2) 입력 단어가 하나도 안 빠졌는지
    missing = [w for w in expect if w not in by_term]
    if missing:
        problems.append(f"배치에서 누락된 단어 {len(missing)}개: {missing}")

    # 환각(요청 안 한 단어가 새로 생김)도 참고용으로 기록
    extra = [t for t in by_term if t not in expect]
    if extra:
        problems.append(f"요청하지 않은 단어가 출력에 새로 생김 {len(extra)}개: {extra}")

    # (1) 철자 변형 그룹이 같은 canonical로 묶였는지
    group_canonicals: dict[str, dict] = {}
    for canonical_key, spec in VARIANT_GROUPS.items():
        seen = {}
        for word in spec["words"]:
            item = by_term.get(word)
            if item is None:
                continue
            seen[word] = item.get("canonical")
        group_canonicals[canonical_key] = seen
        distinct = set(seen.values())
        if len(distinct) > 1:
            problems.append(
                f"[{canonical_key}] 그룹 안에서 canonical이 갈림(묶기 실패): {seen}"
            )
        # (3)/(4) exclude·polarity 기대치 확인 (그룹당 하나라도 다르면 문제로 기록)
        expect_polarity = spec["expect_polarity"]
        if expect_polarity is not None:
            for word, item in ((w, by_term.get(w)) for w in spec["words"]):
                if item is None:
                    continue
                if item.get("polarity") != expect_polarity:
                    problems.append(
                        f"[{canonical_key}] '{word}' polarity 기대={expect_polarity!r} "
                        f"실제={item.get('polarity')!r}"
                    )

    # 채움용 단어들도 exclude/극단적 오분류만 가볍게 체크(전수 정답 검증은 아님 — 채움 목적이라)
    for word, meta in expect.items():
        if meta["group"] is not None:
            continue
        item = by_term.get(word)
        if item is None:
            continue
        if meta["expect_polarity"] == "exclude" and item.get("polarity") != "exclude":
            problems.append(
                f"[채움] '{word}' exclude여야 하는데 실제={item.get('polarity')!r}"
            )

    ok = len(problems) == 0
    return ok, problems, group_canonicals


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

    payload, expect = build_batch()
    print(f"모델: {model_id} | reasoning_effort: {reasoning_effort} | 배치 크기: {len(payload)}단어")
    print("=" * 70)

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    # 100개 항목 출력은 토큰이 많이 필요함(항목당 대략 30~40토큰) — 2-8/2-6b보다 max_tokens를
    # 넉넉히 잡음. reasoning_effort가 low보다 높으면 추론 토큰까지 더 필요할 수 있음.
    max_tokens = 8000
    try:
        resp = model.chat(
            messages=messages,
            params={"temperature": 0, "max_tokens": max_tokens, "reasoning_effort": reasoning_effort},
        )
    except Exception as e:
        print(f"[에러] API 호출 실패: {type(e).__name__}: {e}")
        sys.exit(1)

    msg = resp["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        print("[실패] 본문이 비어있음 (토큰 부족/reasoning만 나왔을 가능성 — max_tokens를 더 올려보세요)")
        RESULT_PATH.write_text(json.dumps({"raw": None, "payload": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(1)

    try:
        parsed = json.loads(strip_fences(content))
    except json.JSONDecodeError as e:
        print(f"[실패] JSON 파싱 실패: {e}")
        print("원본 응답 앞부분:", content[:500])
        RESULT_PATH.write_text(json.dumps({"raw": content, "payload": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(1)

    ok, problems, group_canonicals = validate(parsed, expect)

    print(f"\n[전체] 입력 {len(payload)}개 / 출력 {len(parsed) if isinstance(parsed, list) else '?'}개")
    print(f"[결과] {'✓ 통과' if ok else '✗ 문제 있음'}")
    for p in problems:
        print(f"  - {p}")

    print("\n[그룹별 canonical 실제 결과] (묶였는지 + 어떤 표기를 대표형으로 골랐는지 확인용)")
    for canonical_key, seen in group_canonicals.items():
        print(f"  {canonical_key}: {seen}")

    RESULT_PATH.write_text(
        json.dumps(
            {"payload": payload, "parsed": parsed, "ok": ok, "problems": problems, "group_canonicals": group_canonicals},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n전체 원본 결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
