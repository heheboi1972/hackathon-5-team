# 1-V4 테스트 키트 — gpt-oss 해석 문장(highlights) 품질 확인

담당: 윤아 | 참고: `api/app/prompts/interpret.md` (계약), `api/mock/report_stored.json` (실제 출력 예시)

## 사용법

1. watsonx.ai 콘솔 → 팀 프로젝트 → **Prompt Lab** 열기
2. 모델: `openai/gpt-oss-120b` 선택. 파라미터에 `reasoning_effort`가 노출되면 **low**로 설정 (없으면 그냥 진행 — 코드에서는 낮게 주는데, Prompt Lab UI엔 없을 수도 있음)
3. 아래 "① 시스템 프롬프트"를 System 영역에 붙여넣기 (10번 테스트 내내 고정)
4. 아래 "② 테스트 입력 10개"를 하나씩 User 영역에 붙여넣고 실행 → 결과를 "③ 체크리스트"에 표시
5. 다 돌리고 나서 마지막 "④ 종합 판단"에 정리

---

## ① 시스템 프롬프트 (초안 — 테스트하면서 다듬을 것)

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
      "evidence": [ evidence_candidates 중에서 고른 항목 ],
      "sources": [ knowledge 중에서 고른 항목 ]
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
6. 톤은 판정하는 관찰자가 아니라, 이 관계를 오래 지켜본 다정한 친구처럼 따뜻하게.
   단정적이거나 평가하는 말투("문제가 있다", "안 좋다")는 피한다.

JSON 외의 다른 텍스트(설명, 인사말)는 출력하지 않는다.
```

---

## ② 테스트 입력 10개

각 입력을 User 메시지로 붙여넣으세요. (실제 서비스에서는 이 JSON을 코드가 자동으로 만들어서 넘깁니다.)

**입력 1 — 질문 빈도 감소 (약하게)**
```json
{"metric": "question_rate", "direction": "down", "magnitude": "slight",
 "knowledge": [{"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"}],
 "evidence_candidates": [{"session_id": 1102, "at": "2026-07-22T21:05:00+09:00", "snippet": "오늘 뭐 했어?"}]}
```

**입력 2 — 질문 빈도 증가 (눈에 띄게)**
```json
{"metric": "question_rate", "direction": "up", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "관심 표현으로서의 질문"}],
 "evidence_candidates": [{"session_id": 1150, "at": "2026-08-10T20:12:00+09:00", "snippet": "너 요즘 취미 뭐야?"}]}
```

**입력 3 — 메시지 길이 감소 (눈에 띄게) — "짧아졌다"를 부정적으로 안 쓰는지 확인용**
```json
{"metric": "message_length_median", "direction": "down", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "짧은 답장의 의미"}],
 "evidence_candidates": [{"session_id": 1201, "at": "2026-08-15T22:30:00+09:00", "snippet": "ㅇㅇ"}]}
```

**입력 4 — 메시지 길이 증가 (약하게)**
```json
{"metric": "message_length_median", "direction": "up", "magnitude": "slight",
 "knowledge": [], "evidence_candidates": []}
```
*(지식/근거 후보가 둘 다 비어있는 케이스 — sources/evidence를 지어내지 않고 빈 배열로 두는지 확인)*

**입력 5 — 답장 간격 증가 (눈에 띄게) — 두 사람 비교 유혹이 큰 케이스**
```json
{"metric": "reply_gap_median_min", "direction": "up", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "응답 속도와 상황"}],
 "evidence_candidates": [{"session_id": 1187, "at": "2026-08-19T23:41:00+09:00", "snippet": "미안 지금 봤어"}]}
```

**입력 6 — 답장 간격 감소 (약하게)**
```json
{"metric": "reply_gap_median_min", "direction": "down", "magnitude": "slight",
 "knowledge": [{"doc": "communication_basics.md", "section": "응답 속도와 상황"}],
 "evidence_candidates": [{"session_id": 1210, "at": "2026-08-21T13:05:00+09:00", "snippet": "ㅋㅋ바로답장"}]}
```

**입력 7 — 대화 재개 지연 증가 (눈에 띄게)**
```json
{"metric": "resume_delay_median_min", "direction": "up", "magnitude": "clear",
 "knowledge": [{"doc": "communication_basics.md", "section": "대화 공백의 의미"}],
 "evidence_candidates": [{"session_id": 1230, "at": "2026-08-18T09:15:00+09:00", "snippet": "다시 왔어"}]}
```

**입력 8 — 대화 재개 지연 감소 (약하게)**
```json
{"metric": "resume_delay_median_min", "direction": "down", "magnitude": "slight",
 "knowledge": [], "evidence_candidates": [{"session_id": 1245, "at": "2026-08-22T19:00:00+09:00", "snippet": "바로 답장왔네"}]}
```

**입력 9 — 근거 후보가 여러 개 있는 케이스 (엉뚱한 걸 고르지 않는지 확인)**
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

## ③ 체크리스트 (10개 결과 각각 확인)

| # | JSON 형식 맞음 | observation 1문장/무주어 | interpretations 2개+/종결어미 없음 | 숫자 없음 | 사람 비교 없음 | evidence/sources 후보 안에서만 | 톤(다정한 친구) | 종합 |
|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |
| 6 | | | | | | | | |
| 7 | | | | | | | | |
| 8 | | | | | | | | |
| 9 | | | | | | | | |
| 10 | | | | | | | | |

칸마다 ✓ / ✗만 표시하고, ✗면 어떤 문장이 왜 걸렸는지 옆에 한 줄 메모.

---

## ④ 종합 판단 (10개 다 돌린 후 작성)

- 10개 중 몇 개가 6개 규칙을 전부 통과했는지: ___ / 10
- 자주 깨지는 규칙이 있다면 무엇인지 (예: 종결어미를 자꾸 붙인다, 가끔 숫자를 지어낸다 등):
- 이 정도 품질이면 그대로 써도 되는지 / 시스템 프롬프트를 다듬어야 하는지 / 아예 다른 모델(대안)이 필요한지:
- 통과율이 낮다면 어디를 먼저 고칠지 (프롬프트 문구 vs 다른 모델):

이 결과를 바탕으로 `interpret.md`의 "## 지시문" 부분을 최종 확정해서 채워 넣으면 V4 완료.
