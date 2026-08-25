"""질의를 임베딩하고 Qdrant 대화 검색 서비스에 위임하는 tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ..services.ai_service import AIService
from ..services.qdrant_service import QdrantService


async def search_conversation(
    couple_id: UUID | str,
    query: str,
    start: datetime | None = None,
    end: datetime | None = None,
    k: int = 8,
    *,
    ai: AIService,
    qdrant: QdrantService,
) -> list[dict[str, Any]]:
    search = getattr(qdrant, "search_conversation", None)
    if search is None:
        raise RuntimeError("Qdrant search_conversation 저장소 경로가 아직 구현되지 않았습니다")
    vector = await ai.embed_query(query)
    rows = await search(couple_id, vector, k=k, start=start, end=end)
    return [dict(item) for item in rows]
