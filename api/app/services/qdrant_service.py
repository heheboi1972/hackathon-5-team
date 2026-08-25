# 역할: Qdrant 컬렉션 A(대화 세션) 관리 — upsert, search(couple_id 필터), delete_by_couple (참조: TRD §4.2)
# 컬렉션 B(지식·템플릿)는 Qdrant 에 두지 않음 → container.knowledge 메모리 dict (ISSUE D2)
# upsert_sessions: embed_sessions.py(TASKS 2-6, 윤아)가 호출.
# search_conversation: tools/search_conversation.py(TASKS 3-1)가 호출 — 여기선 벡터·메타만 다루고
#   인용 본문은 툴 쪽에서 Postgres 복호화로 채운다.
from __future__ import annotations

import logging
from datetime import datetime

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

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
            logger.warning(
                "qdrant 컬렉션 %s 차원 불일치 (%d → %d): 재생성. 기존 포인트 삭제됨",
                name,
                current,
                vector_size,
            )
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

    async def delete_by_couple(self, couple_id: str) -> None:
        """커플 해제 시 해당 payload의 모든 벡터를 동기 삭제한다."""
        await self.client.delete(
            collection_name=self.collection_conv,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="couple_id", match=MatchValue(value=str(couple_id))
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def upsert_sessions(self, couple_id, points: list[dict]) -> None:
        """embed_sessions 잡(services/embed_sessions.py, TASKS 2-6)에서 호출.
        points: [{"id","vector","payload"}, ...] — id는 이미 결정론적 UUID로 만들어져 있어서
        (embed_sessions.build_points, 근거는 그 파일 상단 주석) 재업로드로 같은 청크가 다시 임베딩돼도
        upsert 로 덮어쓰기만 되고 중복 포인트가 쌓이지 않는다.
        (윤아가 2-6 범위로 먼저 채워둠 — 실제 Qdrant 인프라에서 point id 제약 등 검수 부탁, 윤석)"""
        if not points:
            return
        await self.client.upsert(
            collection_name=self.collection_conv,
            points=[
                PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
                for p in points
            ],
            wait=True,
        )

    async def search_conversation(
        self,
        couple_id,
        vector: list[float],
        k: int = 8,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """벡터 검색 + couple_id 필터 (+ 선택적 기간 필터) → [{session_id, chunk_idx, score}].

        본문·발화자는 payload 에 없다 — 인용 카드는 호출자(tools/search_conversation.py)가
        Postgres 에서 복호화해 만든다.

        기간 필터는 "청크 구간이 [start, end] 와 겹치는가"로 건다: `ended_at >= start` AND
        `started_at <= end`. 걸러낸 뒤 top-k 를 뽑으므로, 범위를 좁혀도 그 안에서 가장 가까운
        k개가 나온다 (전체에서 k개 뽑고 나중에 버리면 범위 안 결과가 0건이 될 수 있다)."""
        must: list = [
            FieldCondition(key="couple_id", match=MatchValue(value=str(couple_id)))
        ]
        if start is not None:
            must.append(FieldCondition(key="ended_at", range=Range(gte=start.timestamp())))
        if end is not None:
            must.append(FieldCondition(key="started_at", range=Range(lte=end.timestamp())))

        result = await self.client.query_points(
            collection_name=self.collection_conv,
            query=vector,
            query_filter=Filter(must=must),
            limit=k,
            with_payload=True,
        )
        return [
            {
                "session_id": p.payload["session_id"],
                "chunk_idx": p.payload["chunk_idx"],
                "score": p.score,
            }
            for p in result.points
        ]
