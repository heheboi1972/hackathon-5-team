# 역할: 단어 횟수 검색 툴 — services/term_search.count_term 래퍼, OTel 스팬 tool.count_term
#      (참조: API_SPEC §8, §6.1 term_count)
# 커플 합산만 반환한다. 발화자별 횟수는 계산하지 않는다 (P-3 예외 보호).
# 시그니처: (couple_id, term, start=None, end=None) -> {term, total, matched_forms, by_week}
# TODO(윤석): term_search.count_term 연결 (캐시 조회 → 미스 시 to_thread 복호화 카운트)
