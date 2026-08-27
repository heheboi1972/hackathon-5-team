# 역할: 최다 사용 단어 조회 툴 — services/term_search.TermSearchService.top_terms 래퍼
#      (참조: count_term.py와 동일 패턴, chat_supervisor의 top_term 선분기 전용)
# 커플 합산 빈도 상위 N개만 반환한다. 발화자별 순위는 계산하지 않는다 (P-3 예외 보호).
# 시그니처: (couple_id, start=None, end=None, limit=5) -> {terms: [{term, count}, ...]}
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ..services.term_search import TermSearchService


async def top_terms(
    couple_id: UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 5,
    service: TermSearchService,
) -> dict[str, Any]:
    """LLM을 거치지 않고 TermSearchService의 결정론적 결과만 반환한다."""
    return await service.top_terms(couple_id, start=start, end=end, limit=limit)
