# chat_intent (챗봇 intent 분류)

TODO: 윤아

고정 규칙 (ISSUE A3):
- 횟수·빈도 질문("~몇 번 썼어?", "~얼마나 자주")은 `other` 로 분류한다. 현재 구조(벡터 검색 상위 8개)로는 정확한 횟수를 셀 수 없어 틀린 숫자를 말할 위험이 있음.
  → 안내 문구: "횟수는 아직 세어드릴 수 없어요. 대화 기록·지표·리포트에 대해 물어봐 주세요"
  → Phase 3 `build_lexicon` 이후 `term_count` intent + `count_term` 툴로 교체 (API_SPEC §8)
