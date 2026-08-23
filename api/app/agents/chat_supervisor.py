# 역할: 챗봇 수퍼바이저 — intent 분류 → 툴 → 인용 강제 → 리다이렉트 (참조: FR-006, API_SPEC §6.1, TRD §5.3)
# 분기 순서 (LLM 호출을 줄이려면 결정론 분기를 먼저):
#   1. term_count    : regex 로 "X 몇 번/몇 회/얼마나 자주" 를 잡아 단어 추출 → count_term 툴 → 템플릿 답변 (LLM 0회)
#   2. advice_request: 키워드 regex → 고정 리다이렉트 문구 (LLM 0회)
#   3. 나머지        : 검색 먼저 수행 후 {intent, answer, citations} 를 1회 호출로 받는다
# TODO(윤석): 구현
import re

# term_count 선분기용 패턴 (prompts/chat_intent.md 와 같은 규칙)
COUNT_PATTERN = re.compile(r"(몇\s*번|몇\s*회|얼마나\s*자주)")
QUOTED_TERM = re.compile(r"['\"\u2018\u2019\u201c\u201d]([^'\"\u2018\u2019\u201c\u201d]{1,20})['\"\u2018\u2019\u201c\u201d]")
# "내가/네가/쟤가 몇 번" — 사람을 지목한 질문이어도 합산으로만 답하고 안내 문구를 덧붙인다
PERSON_HINT = re.compile(r"(내가|제가|나는|너가|네가|쟤가|걔가|상대(방)?가)")
