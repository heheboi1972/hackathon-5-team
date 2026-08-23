# 역할: FR-006 단어 횟수 검색 — "사랑해 몇 번 썼어?" (참조: API_SPEC §6.1 term_count, §8 count_term)
#
# 감성 분석과 무관하다. couple_lexicon 은 철자 변형을 넓히는 보조 재료일 뿐,
# 사전에 없는 임의의 단어("치킨", "엄마")도 정확히 센다. LLM 을 쓰지 않는다 (P-2).
#
# 커플 합산만 낸다. 발화자별 횟수는 "숨기는" 게 아니라 **계산하지 않는다** —
# 이 모듈 어디에도 sender 가 등장하지 않고 term_count_cache 에도 컬럼이 없다 (P-3 예외 보호).
#
# 복호화(TRD §4.1 (d)): 캐시 미스일 때만 해당 커플 본문을 메모리에서 풀어 세고 즉시 버린다.
# 평문 본문은 디스크에 쓰지 않으며, 남는 것은 {단어, 주, 횟수} 뿐이다.
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from .kakao_parser import tokenize

logger = logging.getLogger(__name__)

MAX_MATCHED_FORMS = 5   # 답변에 나열할 변형 개수 상한


def normalize_query(q: str) -> str | None:
    """질문에서 뽑은 단어를 본문과 같은 방식으로 정규화. 토큰이 안 나오면 None."""
    toks = tokenize(q)
    return toks[0] if toks else None


def _variants(term: str, lexicon: dict[str, tuple[str, str]] | None) -> set[str]:
    """term 과 같은 canonical 을 갖는 사전 표제어들 (조아/좋앙 → 좋아). 사전이 없으면 빈 집합."""
    if not lexicon:
        return set()
    canon = lexicon.get(term, (term, ""))[0]
    return {t for t, (c, _) in lexicon.items() if c == canon}


def match_tokens(
    tokens: list[str], term: str, lexicon: dict[str, tuple[str, str]] | None = None
) -> list[str]:
    """
    한 메시지의 토큰 중 term 에 해당하는 것들을 반환 (등장 횟수만큼 중복 포함).
    매칭: 완전일치 | 접두일치("사랑" → "사랑해") | 같은 canonical("조아" → "좋아")
    """
    equivalents = _variants(term, lexicon) | {term}
    return [t for t in tokens if t in equivalents or t.startswith(term)]


def count_in_messages(
    msgs: list[tuple[date, list[str]]],
    term: str,
    lexicon: dict[str, tuple[str, str]] | None = None,
) -> dict:
    """
    msgs: [(week_start, tokens)] — 호출자가 복호화·토크나이즈한 결과. sender 는 받지 않는다.
    → {"term", "total", "matched_forms": [{"form","count"}], "by_week": [{"week_start","count"}]}
    """
    by_week: dict[date, int] = defaultdict(int)
    forms: dict[str, int] = defaultdict(int)

    for week_start, tokens in msgs:
        hits = match_tokens(tokens, term, lexicon)
        if hits:
            by_week[week_start] += len(hits)
            for h in hits:
                forms[h] += 1

    return {
        "term": term,
        "total": sum(by_week.values()),
        "matched_forms": [
            {"form": f, "count": c}
            for f, c in sorted(forms.items(), key=lambda x: (-x[1], x[0]))[:MAX_MATCHED_FORMS]
        ],
        "by_week": [{"week_start": w, "count": by_week[w]} for w in sorted(by_week)],
    }


def format_answer(result: dict, asked_about_person: bool = False) -> str:
    """카운트 결과 → 사용자 문구. 인용은 붙이지 않는다(발화자 노출 방지, API_SPEC §6.1 P-4 예외)."""
    term, total = result["term"], result["total"]
    if total == 0:
        return f"'{term}'은 대화 기록에서 찾지 못했어요."

    forms = result["matched_forms"]
    detail = ""
    if len(forms) > 1:
        detail = " (" + " · ".join(f"{f['form']} {f['count']}" for f in forms) + ")"

    line = f"'{term}'은 전체 대화에서 {total}번 나왔어요{detail}."
    if asked_about_person:
        line += " 누가 얼마나 썼는지는 알려드리지 않아요."
    return line


# ------------------------------------------------------------ TODO(윤석): 저장소 연결
# async def count_term(couple_id, term, start=None, end=None) -> dict:
#     term = normalize_query(term)  → None 이면 호출자가 other 로 처리
#     1) SELECT week_start, count FROM term_count_cache WHERE couple_id=? AND term=?  → 히트면 조립해 반환
#     2) 미스: await asyncio.to_thread(_scan)  — 이벤트 루프를 막지 않는다 (18k 메시지 ~1-2s)
#          _scan: SELECT sent_at, body_enc FROM messages WHERE couple_id=?  (sender 는 SELECT 하지 않는다)
#                 → crypto.decrypt → tokenize → [(week_start, tokens)] → count_in_messages
#     3) INSERT INTO term_count_cache ... ON CONFLICT DO UPDATE
#     4) start/end 가 있으면 by_week 를 그 범위로 필터해 total 재계산
#
# 무효화: 업로드 동기 구간 끝에서 DELETE FROM term_count_cache WHERE couple_id = ?
