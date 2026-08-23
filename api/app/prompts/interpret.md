# interpret (에이전트 2: 해석)

## 계약 (고정 — 바꾸려면 API_SPEC §4.2 부터)

**입력** — 코드가 만든다. 숫자도 사람별 값도 들어오지 않는다 (ISSUE B3).
```json
{ "metric": "question_rate", "direction": "down", "magnitude": "slight",
  "knowledge": [...],  "evidence_candidates": [...] }
```
`direction ∈ {up, down}` · `magnitude ∈ {slight, clear}`. `steady`·비교 불가 주차는 애초에 안 온다.

**출력**
```json
{ "highlights": [ { "observation": "...", "interpretations": ["...", "..."],
                    "evidence": [...], "sources": [...] } ] }
```

**규칙**
1. `observation` 은 **관찰 한 문장**. 주어는 항상 "우리"거나 무주어. 특정 인물을 가리키는 말은 쓰지 않는다
2. `interpretations` 는 **2개 이상**, 각 항목은 **종결어미 없는 절** — `"바쁜 시기였을 수도"` (O) / `"바쁜 시기였을 수 있어요."` (X).
   프론트가 `", ".join(...) + " 있어요."` 로 한 문장을 만들어, 카드가 관찰·해석·제안 **3문장**이 된다.
   2개를 강제하는 건 원인을 단정하지 않기 위해서다 (P-1)
3. **숫자를 쓰지 않는다.** 입력에 없으므로 쓰면 지어낸 값이다. 정도는 `magnitude` 를 말로 옮긴다 ("조금", "눈에 띄게")
4. 두 사람을 비교하지 않는다. "더 ~하다", "~보다", "누가 더" 금지. 기준선 비교("지난 4주에 비해")는 사람 비교가 아니므로 허용
5. `evidence` 는 `evidence_candidates` 안에서만, `sources` 는 `knowledge` 안에서만 (P-4)
6. 한국어. 톤은 판정하는 관찰자가 아니라 **이 관계를 오래 지켜본 다정한 친구**

금지 표현은 `banned_patterns.txt` 가 결정론으로 먼저 걸러낸다 (TRD §5.2 검수 2단).

## 지시문

TODO: 윤아 — 위 계약을 지키는 instructions 본문과 톤 예시 (TASKS 2-12)
