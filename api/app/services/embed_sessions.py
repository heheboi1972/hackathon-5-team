# 역할: embed_sessions 잡 핸들러 — 세션을 청크로 나눠 watsonx e5로 임베딩하고 Qdrant 컬렉션 A에 저장 (TASKS 2-6, 윤아)
#
# 임베딩 자체(passage:/query: 접두사, e5 모델 호출)는 ai_service.py 에 이미 구현돼 있음.
# 여기서는: (1) 세션 메시지를 청크 문자열로 나누고, (2) 임베딩 벡터로 Qdrant point 를 구성하고,
#          (3) 잡 진행률(done/failed)을 갱신하는 것까지만 담당한다.
#
# point id: {couple_id}:{session_id}:{chunk_idx} 를 결정론적 UUID(uuid5)로 변환해서 사용한다.
#   TASKS.md/qdrant_service.py 의 원래 표기는 "{session_id}:{chunk_idx}" 문자열이지만,
#   Qdrant 는 point id 로 부호없는 정수 또는 UUID 형식만 허용하고 임의 문자열은 거부한다.
#   그래서 그 키를 그대로 UUID5로 해싱해서 사용 — 같은 (couple_id, session_id, chunk_idx) 는
#   항상 같은 UUID가 나오므로 재업로드 시 "멱등 upsert(덮어쓰기, 중복 안 쌓임)" 속성은 그대로 유지된다.
#   원래 문자열은 payload.point_key 에 그대로 남겨서 디버깅·조회 시 알아볼 수 있게 했다.
#   (윤석 검수 필요 — 실제 Qdrant 인프라에서 point id 제약 한번 확인 부탁)
#
# payload 에는 본문(원문)을 넣지 않는다 — Qdrant 는 벡터+메타데이터만, 원문은 Postgres(Fernet 암호화)에만 존재 (프라이버시).
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any
from uuid import UUID

from .kakao_parser import Message, classify, tokenize

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 700  # e5-large TRUNCATE_INPUT_TOKENS=512 토큰 기준 보수적 추정(한글 토큰 비율 고려, ai_service.py 설정과 정합)


def _line(m: Message) -> str:
    return f"{m.sender.upper()}: {m.body.strip()}"


def format_chunk(group: list[Message]) -> str:
    """청크 메시지 묶음 → 임베딩에 넣을 대화체 문자열 ("A: ...\\nB: ...")."""
    return "\n".join(_line(m) for m in group)


def chunk_session_messages(
    messages: list[Message], max_chars: int = MAX_CHUNK_CHARS
) -> list[list[Message]]:
    """세션 메시지 → 청크별 메시지 묶음.
    text 타입 메시지만 포함한다(사진·이모티콘 등 placeholder 는 검색 의미가 없어 제외).
    메시지 순서를 유지한 채 max_chars 를 넘기기 직전에 청크를 끊는다 — 발화 단위가 잘리지 않게.
    한 메시지 혼자 max_chars 보다 길어도 버리지 않고 그 메시지만으로 청크를 만든다(watsonx 가 512 토큰에서 truncate).
    text 메시지가 하나도 없는 세션(사진만 오간 세션 등)은 빈 리스트를 반환한다 — 임베딩 대상에서 자연히 제외.

    문자열이 아니라 Message 묶음을 돌려주는 이유: point payload 에 청크별 시각 범위를 넣어야
    search_conversation 이 기간 필터를 벡터 검색 **안에서** 걸 수 있다 (TASKS 3-1)."""
    usable = [m for m in messages if m.msg_type == "text" and m.body.strip()]
    if not usable:
        return []

    groups: list[list[Message]] = []
    cur: list[Message] = []
    cur_len = 0
    for m in usable:
        line_len = len(_line(m)) + 1
        if cur and cur_len + line_len > max_chars:
            groups.append(cur)
            cur = []
            cur_len = 0
        cur.append(m)
        cur_len += line_len
    if cur:
        groups.append(cur)
    return groups


def chunk_session_text(messages: list[Message], max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """chunk_session_messages 를 임베딩 입력 문자열로 옮긴 것."""
    return [format_chunk(g) for g in chunk_session_messages(messages, max_chars)]


def build_points(
    couple_id: UUID, session_id: int, groups: list[list[Message]], vectors: list[list[float]]
) -> list[dict[str, Any]]:
    """청크 묶음 + 임베딩 벡터 → Qdrant point 리스트. id 결정론 근거는 파일 상단 주석 참고.

    payload 의 started_at/ended_at 은 **청크 자신의** 첫·마지막 메시지 시각(epoch 초)이다.
    search_conversation 의 기간 필터가 이 값으로 걸린다 — 세션 단위가 아니라 청크 단위라
    긴 세션에서도 범위 밖 구간이 딸려오지 않는다. 본문·발화자는 여전히 넣지 않는다(프라이버시)."""
    points = []
    for idx, (group, vec) in enumerate(zip(groups, vectors)):
        point_key = f"{session_id}:{idx}"
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{couple_id}:{point_key}"))
        points.append(
            {
                "id": point_id,
                "vector": vec,
                "payload": {
                    "couple_id": str(couple_id),
                    "session_id": session_id,
                    "chunk_idx": idx,
                    "point_key": point_key,
                    "started_at": int(group[0].sent_at.timestamp()),
                    "ended_at": int(group[-1].sent_at.timestamp()),
                },
            }
        )
    return points


async def _load_sessions_by_id(container: Any, couple_id: UUID) -> list[tuple[int, list[Message]]]:
    """Postgres에서 couple의 메시지를 읽어 복호화하고 session_id 기준으로 묶는다.
    (routers/upload.py 의 _stored_messages() 와 같은 복호화 패턴 — 원문은 여기서만 잠깐 메모리에 있고 저장 안 됨)"""
    rows = await container.postgres.get_messages_for_embedding(couple_id)
    by_session: dict[int, list[Message]] = defaultdict(list)
    for row in rows:
        body = container.cipher.decrypt(row["body_enc"])
        msg_type = classify(body)
        by_session[row["session_id"]].append(
            Message(
                sender=row["sender"],
                sent_at=row["sent_at"],
                body=body,
                msg_type=msg_type,
                is_question=row["is_question"],
                body_len=row["body_len"],
                tokens=tokenize(body) if msg_type == "text" else [],
            )
        )
    return sorted(by_session.items())


async def run_embed_sessions_job(container: Any, job: dict[str, Any]) -> None:
    """JobService 핸들러 — container.py 의 build_container() 에서 kind="embed_sessions" 로 등록된다.
    job 은 postgres_service.claim_next_job() 이 반환한 행(job_id, couple_id, kind, total, ...).
    세션 하나가 실패해도 잡 전체를 죽이지 않는다 — done/failed 만 갱신하고 계속 진행한다.
    (재업로드하면 같은 point id로 다시 upsert 되므로, 실패했던 세션도 다음 업로드 때 자연히 복구됨)"""
    couple_id: UUID = job["couple_id"]
    job_id = job["job_id"]

    sessions = await _load_sessions_by_id(container, couple_id)
    done = 0
    failed = 0
    for session_id, messages in sessions:
        try:
            groups = chunk_session_messages(messages)
            if groups:
                vectors = await container.ai.embed_documents([format_chunk(g) for g in groups])
                points = build_points(couple_id, session_id, groups, vectors)
                await container.qdrant.upsert_sessions(couple_id, points)
            done += 1
        except Exception:
            logger.exception(
                "embed_sessions 세션 실패: couple_id=%s session_id=%s", couple_id, session_id
            )
            failed += 1
        await container.postgres.update_job_progress(job_id, done=done, failed=failed)
