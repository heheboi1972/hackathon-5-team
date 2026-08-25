# 역할: 대화 검색 툴 — 질문 임베딩 → Qdrant 벡터 검색 → Postgres 복호화로 인용 카드 조립
#      (참조: API_SPEC §8, §6.1 fact_query, TRD §4.2)
#
# 두 저장소를 걸치는 이유: Qdrant 에는 벡터와 메타만 있고 본문·발화자가 없다(프라이버시 —
# 원문은 Postgres 에 Fernet 암호화로만 존재). 그래서 "무엇이 비슷한가"는 Qdrant 가, "무슨 말이었나"는
# Postgres 가 답한다. 평문은 이 함수 안에서만 잠깐 존재하고 어디에도 쓰지 않는다.
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from ..services.embed_sessions import chunk_session_messages
from ..services.kakao_parser import Message, classify
from . import tracer

logger = logging.getLogger(__name__)

SNIPPET_MAX_CHARS = 80


async def search_conversation(
    container: Any,
    couple_id: UUID,
    query: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    k: int = 8,
) -> list[dict]:
    """→ [{session_id, at, sender, snippet, score}] — 점수 내림차순, 최대 k개.

    `at`·`sender`·`snippet` 은 청크의 **첫 메시지** 기준이다. 청크는 여러 발화를 묶은 단위라
    대표 한 줄을 골라야 하는데, 임베딩된 순서 그대로의 첫 줄이 결정론적이고 재현 가능하다
    (질문과 가장 가까운 개별 메시지를 고르려면 메시지마다 임베딩이 필요한데, 그건 저장 단위가 아니다).

    검색 결과가 없으면 빈 리스트다. 챗봇은 이때 지어내지 말고 "찾지 못했다"고 답해야 한다 (P-4).
    """
    with tracer.start_as_current_span("tool.search_conversation") as span:
        span.set_attribute("couple_id", str(couple_id))
        span.set_attribute("k", k)

        vector = await container.ai.embed_query(query)
        hits = await container.qdrant.search_conversation(
            couple_id, vector, k=k, start=start, end=end
        )
        span.set_attribute("hits", len(hits))
        if not hits:
            return []

        rows = await container.postgres.get_messages_in_sessions(
            couple_id, sorted({h["session_id"] for h in hits})
        )
        groups_by_session = _rebuild_chunks(container, rows)

        citations = []
        for hit in hits:
            groups = groups_by_session.get(hit["session_id"], [])
            if hit["chunk_idx"] >= len(groups):
                # 업로드로 세션이 다시 나뉘었는데 재임베딩 전이면 청크 수가 어긋날 수 있다.
                # 잡이 다시 돌면 같은 point id 로 덮어써져 스스로 맞춰지므로 이 건만 건너뛴다.
                logger.warning(
                    "search_conversation 청크 불일치: session_id=%s chunk_idx=%s (청크 %d개)",
                    hit["session_id"], hit["chunk_idx"], len(groups),
                )
                continue
            head = groups[hit["chunk_idx"]][0]
            citations.append({
                "session_id": hit["session_id"],
                "at": head.sent_at,
                "sender": head.sender,
                "snippet": _snippet(head.body),
                "score": hit["score"],
            })
        return citations


def _snippet(body: str) -> str:
    body = " ".join(body.split())
    return body if len(body) <= SNIPPET_MAX_CHARS else body[:SNIPPET_MAX_CHARS] + "…"


def _rebuild_chunks(container: Any, rows: list[dict]) -> dict[int, list[list[Message]]]:
    """복호화한 메시지를 세션별로 묶고, 임베딩 때와 **같은 함수**로 다시 청크를 나눈다.
    chunk_idx 를 payload 에 저장한 순서와 맞추려면 같은 규칙으로 재현해야 한다."""
    by_session: dict[int, list[Message]] = {}
    for row in rows:
        body = container.cipher.decrypt(row["body_enc"])
        by_session.setdefault(row["session_id"], []).append(
            Message(
                sender=row["sender"],
                sent_at=row["sent_at"],
                body=body,
                msg_type=classify(body),
                is_question=row["is_question"],
                body_len=row["body_len"],
            )
        )
    return {sid: chunk_session_messages(msgs) for sid, msgs in by_session.items()}
