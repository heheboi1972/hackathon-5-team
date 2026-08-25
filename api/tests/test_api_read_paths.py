# 역할: 읽기 경로 3개(타임라인·리포트·돌아보기)의 상대 값 미전송 계약 (TC-API-005-13, ISSUE B3)
# 라우터만 마운트한다: DB·Qdrant·watsonx 없이 돌아야 하므로 app.main 은 쓰지 않는다.
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.deps import AuthenticatedUser, current_member, current_user
from app.main import error_shape_handler
from app.routers import reports, review, timeline
from app.utils.json_utils import load_mock

ROOT = Path(__file__).resolve().parents[2]
WEB_MOCK_DIR = ROOT / "web" / "src" / "api" / "mock"

PER_PERSON_KEYS = ("question_rate", "message_length_median", "reply_gap_median_min", "resume_delay_median_min")
BANNED = {"a", "b", "baseline_a", "baseline_b", "delta_a", "delta_b"}
WEEK = "2026-08-17"   # 월요일
COUPLE_ID = UUID("11111111-1111-1111-1111-111111111111")
COUPLE = f"/api/couples/{COUPLE_ID}"


def _partner_value(value):
    if value is None:
        return None
    return value + (0.01 if isinstance(value, float) else 1)


def _stored_timeline_rows() -> list[dict]:
    """프론트 A 응답 fixture를 저장형으로 되돌린 테스트 전용 데이터."""
    projected = json.loads(
        (WEB_MOCK_DIR / "timeline.json").read_text(encoding="utf-8")
    )
    rows = []
    for week in projected["weeks"]:
        summary = deepcopy(week["summary"])
        my_terms = summary.pop("sentiment")
        for key in PER_PERSON_KEYS:
            value = summary[key]
            summary[key] = {
                "couple": value["couple"],
                "a": value["mine"],
                "b": _partner_value(value["mine"]),
            }
        rows.append(
            {
                "week_start": date.fromisoformat(week["week_start"]),
                "report_status": week["report_status"],
                "summary": summary,
                "weekly_terms": {
                    "a": my_terms,
                    "b": {
                        "pos": [{"canonical": "귀여워", "count": 15}],
                        "neg": [{"canonical": "바쁘", "count": 5}],
                    },
                },
                "outlier_count": week["outlier_count"],
                "events": week["events"],
            }
        )
    return rows


class _TimelineRepository:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows if rows is not None else _stored_timeline_rows()

    async def get_timeline(self, couple_id, *, from_=None, to=None):
        assert couple_id == COUPLE_ID
        return [
            deepcopy(row)
            for row in sorted(self.rows, key=lambda item: item["week_start"])
            if (from_ is None or row["week_start"] >= from_)
            and (to is None or row["week_start"] <= to)
        ]

    async def get_report_record(self, couple_id, week_start):
        assert couple_id == COUPLE_ID
        return deepcopy(load_mock("report_stored")) if week_start == date.fromisoformat(WEEK) else None

    async def create_report_job(self, couple_id, week_start):
        assert couple_id == COUPLE_ID and week_start == date.fromisoformat(WEEK)
        return UUID(int=9)


def _client(me: str, timeline_rows: list[dict] | None = None) -> TestClient:
    app = FastAPI()
    for mod in (timeline, reports, review):
        app.include_router(mod.router)
    app.state.container = SimpleNamespace(
        postgres=_TimelineRepository(timeline_rows)
    )
    app.dependency_overrides[current_member] = lambda: me
    return TestClient(app)


def _get(me: str, path: str, timeline_rows: list[dict] | None = None) -> dict:
    r = _client(me, timeline_rows).get(COUPLE + path)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def payloads() -> dict:
    """{경로: (A 응답, B 응답)}"""
    return {
        p: (_get("a", p), _get("b", p))
        for p in ("/timeline", f"/reports/{WEEK}", "/review")
    }


def _metric_dicts(payload: dict) -> list[dict]:
    """응답 안에서 {couple, mine} 형태를 갖는 dict 를 전부 끌어모은다."""
    found: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            if "couple" in node or "mine" in node:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    return found


def _assert_no_private_axis_keys(node) -> None:
    """응답 전체에서 저장 전용 a/b 축 키가 재귀적으로 없어야 한다."""
    if isinstance(node, dict):
        assert not BANNED & set(node), node
        for value in node.values():
            _assert_no_private_axis_keys(value)
    elif isinstance(node, list):
        for value in node:
            _assert_no_private_axis_keys(value)


def test_no_partner_value_on_any_read_path(payloads):
    """표시를 안 하는 게 아니라 전송을 안 한다 — 세 경로 응답 전체를 훑는다."""
    for path, (a, b) in payloads.items():
        for payload in (a, b):
            _assert_no_private_axis_keys(payload)
            dicts = _metric_dicts(payload)
            assert dicts, f"{path}: 지표 dict 를 못 찾음 — 탐색이 헛돌고 있다"
            for d in dicts:
                assert "mine" in d, f"{path}: mine 누락 (투영 빠짐) — {d}"


def test_couple_identical_mine_differs_on_any_read_path(payloads):
    for path, (a, b) in payloads.items():
        da, db = _metric_dicts(a), _metric_dicts(b)
        assert [d["couple"] for d in da] == [d["couple"] for d in db], path
        assert [d["mine"] for d in da] != [d["mine"] for d in db], path


def test_who_is_absent_from_highlights_and_moments(payloads):
    for payload in payloads[f"/reports/{WEEK}"]:
        assert all("who" not in h for h in payload["highlights"])
        assert all("who" not in m for m in payload["moments"])
        assert payload["moments"][0]["value_min"] == 184     # 판정 근거 숫자는 남는다


def test_sentiment_is_requester_own_terms_only(payloads):
    a, b = payloads["/timeline"]
    sa = a["weeks"][0]["summary"]["sentiment"]
    sb = b["weeks"][0]["summary"]["sentiment"]
    assert sa["pos"][0]["canonical"] == "좋아"
    assert sb["pos"][0]["canonical"] == "귀여워"
    ra, rb = payloads[f"/reports/{WEEK}"]
    assert ra["summary"]["sentiment"] != rb["summary"]["sentiment"]


def test_review_scalars_survive_projection(payloads):
    """dict 가 아닌 값(session_length_median, weeks)은 투영을 그대로 통과해야 한다."""
    a, _ = payloads["/review"]
    assert a["metrics"]["range"]["session_length_median"] == 34
    assert a["metrics"]["baseline"]["weeks"] == 8


@pytest.mark.parametrize(("path", "mock_name"), [
    ("/timeline", "timeline"),
    (f"/reports/{WEEK}", "report_generated"),
])
def test_frontend_mock_matches_projected_stored_form(payloads, path, mock_name):
    """프론트 목(VITE_USE_MOCK)은 저장형을 A 로 투영한 결과여야 한다 — 백/프론트 목 드리프트 방지."""
    web = json.loads((WEB_MOCK_DIR / f"{mock_name}.json").read_text(encoding="utf-8"))
    assert payloads[path][0] == web


def test_non_monday_week_start_is_400():
    r = _client("a").get(f"{COUPLE}/reports/2026-08-18")   # 화요일
    assert r.status_code == 400


def test_report_not_found_and_regenerate_queue_contract():
    missing = _client("a").get(f"{COUPLE}/reports/2026-08-10")
    assert missing.status_code == 404
    queued = _client("a").post(f"{COUPLE}/reports/{WEEK}/regenerate")
    assert queued.status_code == 202
    assert queued.json() == {"job_id": str(UUID(int=9))}


def test_timeline_api_contract_with_25_weeks_and_range_filter():
    """TC-API-004-1~5: repository 대역으로 라우터 읽기 계약을 검증한다."""
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    first_monday = current_monday - timedelta(weeks=24)
    template = _stored_timeline_rows()[0]
    weeks = []
    for offset in range(25):
        stored = deepcopy(template)
        stored["week_start"] = first_monday + timedelta(weeks=offset)
        stored["report_status"] = "generated"
        weeks.append(stored)
    weeks.reverse()  # 저장소 반환 순서에 의존하지 않아야 한다.
    del weeks[0]["report_status"]  # 현재 주 리포트 생성 전

    payload = _get("a", "/timeline", weeks)
    assert len(payload["weeks"]) == 25
    starts = [date.fromisoformat(week["week_start"]) for week in payload["weeks"]]
    assert starts == sorted(starts)
    assert all(week_start.weekday() == 0 for week_start in starts)
    assert payload["weeks"][-1]["in_progress"] is True
    assert payload["weeks"][-1]["report_status"] == "pending"

    expected_summary_keys = {
        "session_count", "message_count", "question_rate",
        "message_length_median", "reply_gap_median_min",
        "resume_delay_median_min", "session_length_median",
        "activity", "sentiment",
    }
    assert set(payload["weeks"][0]["summary"]) == expected_summary_keys
    activity = payload["weeks"][0]["summary"]["activity"]
    assert len(activity["by_weekday"]) == 7
    assert len(activity["by_hour"]) == 24
    _assert_no_private_axis_keys(payload)

    range_from, range_to = starts[5], starts[8]
    filtered = _get(
        "a", f"/timeline?from={range_from}&to={range_to}", weeks
    )
    assert [week["week_start"] for week in filtered["weeks"]] == [
        week_start.isoformat() for week_start in starts[5:9]
    ]


@pytest.mark.parametrize(
    ("user_couple_id", "member"),
    [
        (UUID("22222222-2222-2222-2222-222222222222"), "a"),
        (COUPLE_ID, None),
    ],
)
def test_timeline_rejects_non_member_with_contract_error(user_couple_id, member):
    app = FastAPI()
    app.include_router(timeline.router)
    app.add_exception_handler(HTTPException, error_shape_handler)
    app.state.container = SimpleNamespace(postgres=_TimelineRepository())
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        user_id=uuid4(),
        email="other@example.com",
        display_name="other",
        couple_id=user_couple_id,
        member=member,
        couple_status="active",
    )

    response = TestClient(app).get(f"{COUPLE}/timeline")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "NOT_COUPLE_MEMBER",
            "message": "해당 커플의 구성원이 아닙니다",
        }
    }
