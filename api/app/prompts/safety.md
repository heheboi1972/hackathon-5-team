# safety (에이전트 4: 검수)

## 계약 (고정)

**2단 검수** (TRD §5.2): `banned_patterns.txt` regex 가 먼저 훑고(결정론·빠름), **걸린 문장만** LLM 이 재작성한다.

**검수 대상**: LLM 이 만든 문장 — `highlights[].observation` / `interpretations[]` / `suggestions[].text`
**대상 아님**: `moments[].text` (코드 생성, 수치가 근거) · `summary` · `metrics`

**검사 시점**: `names.ts` 가 A/B → 실명으로 바꾸기 **전**, 서버에서. 그래서 인물 규칙은 A/B 토큰 기준이다.

**출력**: `{ "passed": bool, "rewritten": [{"before": "...", "after": "..."}] }`

**재작성 규칙**
1. 인물 지목 → 무주어 또는 "우리"로. 문장의 사실 내용은 유지
2. 수치 → 정도를 나타내는 말로 ("30% 줄었어요" → "좀 줄어들었어요")
3. 명령 → 권유로 ("~하세요" → "~해보면 어떨까요")
4. 점수·등급·가치 판단·원인 단정·관계 판정 → 재작성이 어려우면 **해당 문장을 뺀다**
5. 재작성 결과도 `banned_patterns.txt` 를 통과해야 한다 (재검사 1회)

## 지시문

TODO: 윤아 — 위 계약을 지키는 instructions 본문 + 검수 규칙표 (TASKS 2-12)
