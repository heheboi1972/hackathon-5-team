# 1-V4 재테스트 — evidence/sources 형식 보강

10개 중 3, 5, 9, 10번에서 `evidence`/`sources`가 정해진 객체 형태 대신 문자열로 축약되어 나온 문제를 고치기 위한 재테스트. 시스템 프롬프트의 5번 규칙에 "객체 형태 유지, 문자열 축약 금지"를 명시적으로 추가했다.

## 사용법

1. Prompt Lab 지시문 칸의 내용을 아래 "① 개정 시스템 프롬프트"로 **교체**
2. "최대 토큰"은 지난번처럼 2000 유지
3. 아래 4개 입력을 순서대로 넣고 "생성" → `assistantfinal` 뒤 최종 JSON만 확인
4. 체크리스트에 표시

---

## ① 개정 시스템 프롬프트

```
너는 커플의 카톡 대화 데이터를 오래 지켜본 다정한 친구야. 아래 규칙을 지키면서
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
   **evidence와 sources는 항상 후보에 있는 객체(object) 형태 그대로 넣는다.**
   예: evidence 올바른 예 → {"session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?"}
       evidence 잘못된 예(금지) → "오늘 뭐 했어?" 처럼 문자열 하나로 축약하는 것
   sources도 마찬가지로 {"doc": "...", "section": "..."} 객체 그대로 넣는다.
   snippet이나 doc 이름만 뽑아서 문자열로 단순화하지 않는다.
6. 톤은 판정하는 관찰자가 아니라, 이 관계를 오래 지켜본 다정한 친구처럼 따뜻하게.
   단정적이거나 평가하는 말투("문제가 있다", "안 좋다")는 피한다.

JSON 외의 다른 텍스트(설명, 인사말)는 출력하지 않는다.
```

---

## ② 재테스트 입력 4개 (기존 3, 5, 9, 10번 그대로)

**입력 3 — 메시지 길이 감소 (눈에 띄게)**
```json
{"metric": "message_length_median", "direction": "down", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "짧은 답장의 의미"}],
 "evidence_candidates": [{"session_id": 1201, "at": "2026-08-15T22:30:00+09:00", "snippet": "ㅇㅇ"}]}
```

**입력 5 — 답장 간격 증가 (눈에 띄게)**
```json
{"metric": "reply_gap_median_min", "direction": "up", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "응답 속도와 상황"}],
 "evidence_candidates": [{"session_id": 1187, "at": "2026-08-19T23:41:00+09:00", "snippet": "미안 지금 봤어"}]}
```

**입력 9 — 근거 후보가 여러 개 있는 케이스**
```json
{"metric": "question_rate", "direction": "down", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"},
               {"doc": "conflict_patterns.md", "section": "회피형 대화"}],
 "evidence_candidates": [{"session_id": 1301, "at": "2026-08-05T21:00:00+09:00", "snippet": "그냥 그랬어"},
                          {"session_id": 1302, "at": "2026-08-06T22:10:00+09:00", "snippet": "몰라 피곤해"}]}
```

**입력 10 — 부정적으로 읽히기 쉬운 지표 (톤 유지 확인용)**
```json
{"metric": "message_length_median", "direction": "down", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "짧은 답장의 의미"}],
 "evidence_candidates": [{"session_id": 1320, "at": "2026-08-20T23:50:00+09:00", "snippet": "응"}]}
```

---

## ③ 체크리스트

| # | evidence 객체 형태 유지 | sources 객체 형태 유지 | 기존 6개 규칙(내용) 그대로 통과 | 종합 |
|---|---|---|---|---|
| 3 | | | | |
| 5 | | | | |
| 9 | | | | |
| 10 | | | | |

## ④ 종합 판단

- 4개 다 객체 형태로 나오면: 프롬프트 보강으로 해결됨 → 대안 모델 불필요, 이 프롬프트를 `interpret.md`에 최종 반영
- 여전히 문자열로 나오는 게 있으면: 자연어 지시만으로는 한계 → watsonx의 구조화 출력(JSON 스키마 강제) 옵션을 팀에 제안하거나, 코드 쪽에서 후처리(문자열이면 원본 후보에서 다시 매칭해서 객체로 복원)하는 방어 로직 추가 검토
