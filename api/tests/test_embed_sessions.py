# TASKS 2-6 — chunk_session_text()/build_points() 순수 함수 테스트.
# run_embed_sessions_job()은 실 Postgres/Qdrant/watsonx 필요 — DB·인프라 뜬 뒤 스모크 테스트로 별도 확인 필요 (윤아, 미완료).
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

from app.services.embed_sessions import build_points, chunk_session_text
from app.services.kakao_parser import Message

_TZ = ZoneInfo("Asia/Seoul")


def _msg(sender: str, body: str, msg_type: str = "text", at: datetime | None = None) -> Message:
    return Message(
        sender=sender,
        sent_at=at or datetime(2026, 8, 24, 12, 0, tzinfo=_TZ),
        body=body,
        msg_type=msg_type,
        is_question=False,
        body_len=len(body),
    )


def test_short_session_one_chunk():
    msgs = [_msg("a", "뭐해?"), _msg("b", "공부")]
    assert chunk_session_text(msgs) == ["A: 뭐해?\nB: 공부"]


def test_photo_only_session_returns_empty():
    msgs = [_msg("a", "", "photo")]
    assert chunk_session_text(msgs) == []


def test_empty_body_text_message_skipped():
    msgs = [_msg("a", "   "), _msg("b", "안녕")]
    assert chunk_session_text(msgs) == ["B: 안녕"]


def test_long_session_splits_into_multiple_chunks():
    line = "가나다라마바사아자차카타파하" * 10  # 약 140자
    msgs = [_msg("a" if i % 2 == 0 else "b", line) for i in range(20)]
    chunks = chunk_session_text(msgs, max_chars=700)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 700 + 200  # 여유치: 단일 메시지 하나가 max_chars를 넘기면 그 줄 하나만으로 청크가 될 수 있음


def test_single_oversized_message_kept_whole_not_dropped():
    msgs = [_msg("a", "가" * 2000)]
    chunks = chunk_session_text(msgs, max_chars=700)
    assert len(chunks) == 1
    assert len(chunks[0]) > 700  # 자르지 않음 — watsonx 쪽 TRUNCATE_INPUT_TOKENS=512 에서 처리


def test_message_order_preserved_within_chunk():
    msgs = [_msg("a", "하나"), _msg("b", "둘"), _msg("a", "셋")]
    assert chunk_session_text(msgs) == ["A: 하나\nB: 둘\nA: 셋"]


def test_build_points_ids_are_deterministic_for_idempotent_reupload():
    couple_id = uuid4()
    groups = [[_msg("a", "하나")], [_msg("b", "둘")]]
    points_v1 = build_points(couple_id, 123, groups, [[0.1, 0.2], [0.3, 0.4]])
    # 같은 (couple_id, session_id, chunk_idx) 면 벡터 값이 달라도(재업로드로 텍스트가 조금 바뀌어도) 같은 id → upsert 로 덮어쓰기만 됨
    points_v2 = build_points(couple_id, 123, groups, [[0.9, 0.9], [0.9, 0.9]])
    assert [p["id"] for p in points_v1] == [p["id"] for p in points_v2]


def test_build_points_different_session_ids_get_different_points():
    couple_id = uuid4()
    groups = [[_msg("a", "하나")]]
    a = build_points(couple_id, 1, groups, [[0.1]])
    b = build_points(couple_id, 2, groups, [[0.1]])
    assert a[0]["id"] != b[0]["id"]


def test_build_points_payload_shape():
    couple_id = uuid4()
    group = [_msg("a", "하나"), _msg("b", "둘")]
    points = build_points(couple_id, 42, [group], [[0.1, 0.2]])
    p = points[0]
    assert p["payload"] == {
        "couple_id": str(couple_id),
        "session_id": 42,
        "chunk_idx": 0,
        "point_key": "42:0",
        "started_at": int(group[0].sent_at.timestamp()),
        "ended_at": int(group[-1].sent_at.timestamp()),
    }


def test_build_points_timestamps_span_the_chunks_own_messages():
    """기간 필터가 청크 단위로 걸리려면 각 point 가 자기 청크의 시각 범위를 들고 있어야 한다.
    세션 전체 범위를 넣으면 긴 세션에서 범위 밖 구간까지 검색에 걸린다 (TASKS 3-1)."""
    couple_id = uuid4()
    early = _msg("a", "아침", at=datetime(2026, 8, 24, 9, 0, tzinfo=_TZ))
    late = _msg("b", "밤", at=datetime(2026, 8, 24, 23, 0, tzinfo=_TZ))
    points = build_points(couple_id, 7, [[early], [late]], [[0.1], [0.2]])
    assert points[0]["payload"]["ended_at"] == int(early.sent_at.timestamp())
    assert points[1]["payload"]["started_at"] == int(late.sent_at.timestamp())
    assert points[0]["payload"]["ended_at"] < points[1]["payload"]["started_at"]
