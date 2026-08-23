# 역할: Qdrant 컬렉션 A(대화 세션) 관리 — upsert, search(couple_id 필터), delete_by_couple (참조: TRD §4.2)
# 컬렉션 B(지식·템플릿)는 Qdrant 에 두지 않음 → container.knowledge 메모리 dict (ISSUE D2)
# 스캐폴딩: 클라이언트·컬렉션 보장(차원 검증 포함)·ping만. upsert/search는 TODO(윤석)
from __future__ import annotations

import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self, url: str, collection_conv: str):
        self.client = AsyncQdrantClient(url=url, timeout=10)
        self.collection_conv = collection_conv

    async def ensure_collections(self, vector_size: int) -> None:
        """컬렉션 A 없으면 생성. 있는데 벡터 차원이 다르면(mock 384 ↔ e5 1024 전환) 재생성 — 데이터는 버려짐 (ISSUE E-6)."""
        name = self.collection_conv
        if await self.client.collection_exists(name):
            info = await self.client.get_collection(name)
            current = info.config.params.vectors.size  # 단일 벡터 설정 기준
            if current == vector_size:
                return
            logger.warning("qdrant 컬렉션 %s 차원 불일치 (%d → %d): 재생성. 기존 포인트 삭제됨", name, current, vector_size)
            await self.client.delete_collection(name)
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
    # point id = f"{session_id}:{chunk_idx}" (결정론 → 재업로드 시 멱등 upsert). payload 에 본문 없음.
    # async def upsert_sessions(self, couple_id, points): ...
    # async def search_conversation(self, couple_id, vector, k=8, start=None, end=None): ...
    # async def delete_by_couple(self, couple_id): ...               # 커플 해제 시 동기 삭제
