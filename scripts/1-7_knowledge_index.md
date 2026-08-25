# 1-7 — 지식 문서 출처 목록 (data/knowledge/interpretations)

담당: 윤아 | 날짜: 2026-08-24 | 총 10개, `knowledge.py`의 `load_knowledge()` 파싱 형식(metric/direction/source/doc_type 메타 + 본문)으로 실제 파싱 확인 완료.

## 목록

| 파일 | metric | direction | 한 줄 요약 |
|---|---|---|---|
| question_rate_down_01.md | question_rate | down | 익숙함/편안함으로 인한 감소 |
| question_rate_down_02.md | question_rate | down | 바쁨·서운함으로 인한 감소 (다른 각도) |
| question_rate_up.md | question_rate | up | 호기심·공유할 화제 증가 |
| message_length_median_down.md | message_length_median | down | 편안해져서 핵심만 주고받음 / 피로로 인한 감소 |
| message_length_median_up.md | message_length_median | up | 나눌 이야기가 많아짐 |
| reply_gap_median_min_up_01.md | reply_gap_median_min | up | 일정·업무로 인한 지연 |
| reply_gap_median_min_up_02.md | reply_gap_median_min | up | 부담·서운함으로 인한 지연 (다른 각도) |
| reply_gap_median_min_down.md | reply_gap_median_min | down | 기다림·계획 공유로 인한 단축 |
| resume_delay_median_min_up.md | resume_delay_median_min | up | 생활 패턴 변화로 인한 재개 지연 |
| resume_delay_median_min_down.md | resume_delay_median_min | down | 공통 관심사로 인한 빠른 재개 |

**커버리지**: 4개 지표(question_rate, message_length_median, reply_gap_median_min, resume_delay_median_min) × 각 방향(up/down) 최소 1개씩. question_rate↓와 reply_gap_median_min↑은 해석 각도가 갈릴 수 있어 문서 2개씩 배치(검색 시 여러 후보 중 고르게 하려는 의도, 1-V4 테스트의 "근거 후보 여러 개" 케이스와 동일한 목적).

## 출처에 대한 중요한 안내

**이 문서들의 `source`는 전부 "couple-report 팀 작성"입니다.** 특정 논문이나 심리학 연구를 인용한 게 아니라, 팀이 상식적인 수준에서 "이런 이유일 수도 있다"를 정리한 자체 해석 노트예요. 실제 심리학/커뮤니케이션 연구를 근거로 달고 싶다면 그건 실제 자료를 찾아서 검증한 뒤에 출처를 바꿔야 해요 — 근거 없이 "OO대학 연구에 따르면" 같은 문구를 넣으면 안 됩니다. 지금 상태로는 "사실 주장"이 아니라 "가능성 있는 해석 제안"으로만 쓰이는 게 안전해요 (`interpret.md` 규칙 2와도 일치 — 원인을 하나로 단정하지 않고 여러 가능성을 "~수도"로만 제시).

## 구현 관련 발견 사항

`knowledge.py`의 `load_knowledge()`는 파일당 `section`을 항상 빈 문자열(`""`)로 고정해서 로드해요 (한 파일 = 지식 항목 하나, 섹션 세분화 없음). 그래서 지금 이 10개 문서는 `sources`로 인용될 때 `{"doc": "question_rate_down_01", "section": ""}` 형태로 나갈 거예요. 만약 한 파일 안에서 여러 섹션으로 더 세분화하고 싶다면 `knowledge.py`의 파싱 로직을 확장해야 합니다 (지금은 지원 안 됨) — 당장은 문제 없지만 나중에 문서를 더 정교하게 나누고 싶어지면 이 부분부터 손봐야 한다는 걸 팀에 공유해두면 좋아요.

## 다음 행동

- 여유 되면 나머지 지표(session_length, resume 관련 세부 등)나 다른 방향 조합 추가 검토
- `source` 필드를 실제 근거로 바꾸고 싶다면 팀 논의 필요 (지금은 팀 자체 해석 노트임을 명확히 인지하고 사용)
