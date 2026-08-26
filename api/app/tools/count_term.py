# 역할: 단어 횟수 검색 툴 — services/term_search.count_term 래퍼, OTel 스팬 tool.count_term
#      (참조: API_SPEC §8, §6.1 term_count)
# 커플 합산만 반환한다. 발화자별 횟수는 계산하지 않는다 (P-3 예외 보호).
# 시그니처: (couple_id, term, start=None, end=None) -> {term, total, matched_forms, by_week}
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ..services.term_search import TermSearchService


async def count_term(
    couple_id: UUID,
    query: str,
    mode: str = "exact",
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    service: TermSearchService,
) -> dict[str, Any]:
    """LLM을 거치지 않고 TermSearchService의 결정론적 결과만 반환한다."""
    return await service.count_term(couple_id, query, mode, start=start, end=end)
