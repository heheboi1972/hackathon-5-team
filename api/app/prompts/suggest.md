# suggest (에이전트 3: 제안)

## 계약 (고정 — 바꾸려면 API_SPEC §4.2 부터)

**입력**: `{metric, direction, magnitude, templates: [{template_id, text}], linked_highlight}`
— 해석과 같이 숫자·사람별 값 없음 (ISSUE B3)

**출력**: `{ "suggestions": [ {"linked_highlight": "h1", "template_id": "...", "text": "..."} ] }` — 1~2개

**규칙**
1. **템플릿 풀에서 고른다. 자유 생성 금지.** `template_id` 는 입력 `templates` 안의 것이어야 한다
2. `text` 는 템플릿 본문을 유지한 채 다듬는 정도까지. 템플릿에 없는 사실·수치를 넣지 않는다
3. 주어는 "우리". 특정 인물에게 시키지 않는다
4. **명령·당위 금지** — "~하세요", "~해야 해요" (P-1). 권유형으로: "~해보면 어떨까요", "~해볼 수 있어요"
5. 카드의 **세 번째 문장**이므로 한 문장으로 끝낸다
6. 한국어

## 지시문

TODO: 윤아 — 위 계약을 지키는 instructions 본문 (TASKS 2-12). 템플릿 풀은 TASKS 2-11
