# TASKS 3-1 — 내부 툴 5개 (API_SPEC §8).
# 실 Postgres/Qdrant/watsonx 없이 도는 것만 여기서 본다: 계약(상대 값 미노출, 템플릿 고정 선택),
# 기준선 재계산, 인용 조립. 실 저장소 붙는 경로는 스모크로 별도 확인.
import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.services.knowledge import Knowledge
from app.services.metrics import metrics_from_stored
from app.tools.get_metrics import get_metrics
from app.tools.get_suggestion_templates import get_suggestion_templates
from app.tools.search_conversation import search_conversation
from app.tools.search_knowledge import search_knowledge

_TZ = ZoneInfo("Asia/Seoul")


def _summary(q: float, ml: float, gap: float) -> dict:
    """저장형 summary — 사람별 값이 그대로 들어있다 (투영 전)."""
    return {
        "session_count": 10,
        "message_count": 100,
        "question_rate": {"couple": q, "a": q - 0.02, "b": q + 0.02},
        "message_length_median": {"couple": ml, "a": ml - 1, "b": ml + 1},
        "reply_gap_median_min": {"couple": gap, "a": gap - 1, "b": gap + 1},
        "resume_delay_median_min": {"couple": 60.0, "a": 55.0, "b": 65.0},
        "session_length_median": 12.0,
        "activity": {"top_weekday": 2, "top_hour": 21, "by_weekday": [0] * 7, "by_hour": [0] * 24},
    }


class _FakePostgres:
    def __init__(self, weeks: dict[date, dict]):
        self._weeks = weeks

    async def get_weekly_metrics(self, couple_id, *, start=None, end=None):
        return [
            {"week_start": w, "summary": s, "summary_hash": "x", "outliers": []}
            for w, s in sorted(self._weeks.items())
            if (start is None or w >= start) and (end is None or w <= end)
        ]


# ---------------------------------------------------------------- 지식 dict 툴


def _knowledge() -> Knowledge:
    k = Knowledge()
    k.docs[("question_rate", "down")] = [
        {"doc": f"d{i}", "section": "", "text": "...", "source": "팀 자체 정리"}
        for i in range(7)
    ]
    k.templates[("question_rate", "down")] = [
        {"template_id": "question_rate_down_1", "text": "하나 물어보면 어떨까요"},
        {"template_id": "question_rate_down_2", "text": "오늘 어땠는지 물어볼까요"},
    ]
    return k


def test_search_knowledge_caps_at_k():
    assert len(search_knowledge(_knowledge(), "question_rate", "down", k=5)) == 5


def test_search_knowledge_unknown_key_returns_empty_not_error():
    """없는 (metric, direction) 조합은 빈 목록이다 — interpret 가 지어낼 근거가 없다는 뜻 (P-4)."""
    assert search_knowledge(_knowledge(), "session_length_median", "up") == []


def test_get_suggestion_templates_returns_only_stored_ids():
    """suggest 는 여기서 고르기만 한다 — 반환된 template_id 는 항상 templates.json 안에 있다."""
    got = get_suggestion_templates(_knowledge(), "question_rate", "down")
    assert [t["template_id"] for t in got] == ["question_rate_down_1", "question_rate_down_2"]


# ---------------------------------------------------------------- 기준선 재계산


def test_metrics_from_stored_needs_four_prior_weeks():
    """기준선은 직전 4주 평균이다. 3주치뿐이면 비교 불가로 나와야 한다 (지어낸 기준선 금지)."""
    weeks = [_summary(0.20, 10, 5) for _ in range(3)]
    m = metrics_from_stored(weeks)
    assert m["question_rate"]["comparable"] is False
    assert m["question_rate"]["baseline_couple"] is None


def test_metrics_from_stored_averages_prior_four_weeks_only():
    history = [_summary(0.10, 10, 5) for _ in range(4)]
    target = _summary(0.30, 10, 5)
    m = metrics_from_stored([*history, target])
    assert m["question_rate"]["comparable"] is True
    assert m["question_rate"]["baseline_couple"] == pytest.approx(0.10)
    assert m["question_rate"]["delta_couple"] == pytest.approx(0.20)


# ---------------------------------------------------------------- get_metrics 계약


@pytest.fixture
def five_weeks():
    base = date(2026, 7, 6)  # 월요일
    return {
        date.fromordinal(base.toordinal() + 7 * i): _summary(0.10 + 0.02 * i, 10, 5)
        for i in range(5)
    }


def test_get_metrics_never_exposes_partner_value(five_weeks):
    """지표 노출은 {couple, mine} 뿐 — 상대 값은 표시를 안 하는 수준이 아니라 아예 안 나간다 (ISSUE B3)."""
    out = asyncio.run(get_metrics(_FakePostgres(five_weeks), uuid4(), "a"))
    assert out
    for week in out:
        for key in ("question_rate", "message_length_median", "reply_gap_median_min"):
            metric = week["metrics"][key]
            assert "mine" in metric
            assert "a" not in metric and "b" not in metric
            assert "baseline_b" not in metric and "delta_b" not in metric
        assert "b" not in week["summary"]["question_rate"]


def test_get_metrics_same_week_couple_identical_mine_differs(five_weeks):
    couple_id = uuid4()
    a = asyncio.run(get_metrics(_FakePostgres(five_weeks), couple_id, "a"))
    b = asyncio.run(get_metrics(_FakePostgres(five_weeks), couple_id, "b"))
    qa, qb = a[-1]["metrics"]["question_rate"], b[-1]["metrics"]["question_rate"]
    assert qa["couple"] == qb["couple"]
    assert qa["mine"] != qb["mine"]


def test_get_metrics_single_week_still_uses_earlier_weeks_for_baseline(five_weeks):
    """구간을 좁혀 물어도 기준선은 그 앞 주차로 계산된다 — 안 그러면 첫 주가 늘 comparable:false 다."""
    target = sorted(five_weeks)[-1]
    out = asyncio.run(get_metrics(_FakePostgres(five_weeks), uuid4(), "a", week_start=target))
    assert len(out) == 1
    assert out[0]["week_start"] == target
    assert out[0]["metrics"]["question_rate"]["comparable"] is True


def test_get_metrics_unknown_week_returns_empty(five_weeks):
    out = asyncio.run(get_metrics(_FakePostgres(five_weeks), uuid4(), "a", week_start=date(2020, 1, 6)))
    assert out == []


# ---------------------------------------------------------------- search_conversation 인용 조립


class _FakeContainer:
    """Qdrant 는 벡터·메타만, Postgres 는 암호문만 준다 — 툴이 둘을 합쳐 인용을 만든다."""

    def __init__(self, hits, rows):
        self.ai = SimpleNamespace(embed_query=self._embed)
        self.qdrant = SimpleNamespace(search_conversation=self._search)
        self.postgres = SimpleNamespace(get_messages_in_sessions=self._messages)
        self.cipher = SimpleNamespace(decrypt=lambda b: b.decode("utf-8"))
        self._hits = hits
        self._rows = rows
        self.asked_range = None

    async def _embed(self, text):
        return [0.1, 0.2]

    async def _search(self, couple_id, vector, k=8, start=None, end=None):
        self.asked_range = (start, end)
        return self._hits

    async def _messages(self, couple_id, session_ids):
        return [r for r in self._rows if r["session_id"] in set(session_ids)]


def _row(session_id: int, sender: str, body: str, hour: int) -> dict:
    return {
        "session_id": session_id,
        "sender": sender,
        "sent_at": datetime(2026, 8, 24, hour, 0, tzinfo=_TZ),
        "body_enc": body.encode("utf-8"),
        "body_len": len(body),
        "is_question": False,
    }


def test_search_conversation_builds_citation_from_decrypted_body():
    rows = [_row(11, "a", "제주도 언제 갈까", 20), _row(11, "b", "다음 달 어때", 20)]
    container = _FakeContainer([{"session_id": 11, "chunk_idx": 0, "score": 0.87}], rows)
    got = asyncio.run(search_conversation(container, uuid4(), "제주도 얘기"))
    assert got == [{
        "session_id": 11,
        "at": rows[0]["sent_at"],
        "sender": "a",
        "snippet": "제주도 언제 갈까",
        "score": 0.87,
    }]


def test_search_conversation_passes_range_down_to_vector_search():
    """기간 필터는 검색 뒤에 거르는 게 아니라 Qdrant 로 내려가야 한다 — 안 그러면 범위 안 결과가 0건이 될 수 있다."""
    container = _FakeContainer([], [])
    start = datetime(2026, 8, 1, tzinfo=_TZ)
    end = datetime(2026, 8, 31, tzinfo=_TZ)
    asyncio.run(search_conversation(container, uuid4(), "질문", start=start, end=end))
    assert container.asked_range == (start, end)


def test_search_conversation_no_hits_returns_empty():
    container = _FakeContainer([], [])
    assert asyncio.run(search_conversation(container, uuid4(), "없는 얘기")) == []


def test_search_conversation_skips_stale_chunk_index_instead_of_crashing():
    """재업로드로 세션이 다시 나뉘었는데 재임베딩 전이면 chunk_idx 가 어긋날 수 있다.
    잡이 다시 돌면 같은 point id 로 덮어써지므로, 그 건만 건너뛰고 나머지는 답한다."""
    rows = [_row(11, "a", "안녕", 20)]
    container = _FakeContainer(
        [{"session_id": 11, "chunk_idx": 9, "score": 0.9},
         {"session_id": 11, "chunk_idx": 0, "score": 0.5}],
        rows,
    )
    got = asyncio.run(search_conversation(container, uuid4(), "인사"))
    assert [c["snippet"] for c in got] == ["안녕"]


def test_search_conversation_truncates_long_snippet():
    body = "가" * 200
    container = _FakeContainer([{"session_id": 3, "chunk_idx": 0, "score": 0.5}], [_row(3, "b", body, 9)])
    got = asyncio.run(search_conversation(container, uuid4(), "질문"))
    assert got[0]["snippet"].endswith("…")
    assert len(got[0]["snippet"]) == 81
