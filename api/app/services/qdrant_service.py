# 역할: Qdrant 컬렉션 A/B 관리 — upsert, search(couple_id 필터), delete_by_couple (참조: TRD §4.2)
# 스캐폴딩: 클라이언트·컬렉션 보장·ping만. upsert/search는 TODO(윤석)
from __future__ import annotations

import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self, url: str, collection_conv: str, collection_knowledge: str):
        self.client = AsyncQdrantClient(url=url, timeout=10)
        self.collection_conv = collection_conv
        self.collection_knowledge = collection_knowledge

    async def ensure_collections(self, vector_size: int) -> None:
        """컬렉션 A(대화 세션)·B(지식) 없으면 생성. e5=1024, mock=384 (TRD §4.2)."""
        for name in (self.collection_conv, self.collection_knowledge):
            if not await self.client.collection_exists(name):
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                logger.info("qdrant 컬렉션 생성: %s (size=%d)", name, vector_size)

    async def ping(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception as e:
            logger.warning("qdrant ping 실패: %s", e)
            return False

    async def close(self) -> None:
        await self.client.close()

    # ------------------------------------------------------------ TODO(윤석)
    # async def upsert_sessions(self, couple_id, points): ...        # 컬렉션 A, 본문 없음
    # async def search_conversation(self, couple_id, vector, k=8, start=None, end=None): ...
    # async def search_knowledge(self, vector, metric=None, direction=None, doc_type=None, k=5): ...
    # async def delete_by_couple(self, couple_id): ...               # 커플 해제 시 동기 삭제
