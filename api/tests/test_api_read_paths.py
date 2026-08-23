# 역할: 읽기 경로 3개(타임라인·리포트·돌아보기)의 상대 값 미전송 계약 (TC-API-005-13, ISSUE B3)
# 라우터만 마운트한다: DB·Qdrant·watsonx 없이 돌아야 하므로 app.main 은 쓰지 않는다.
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import current_member
from app.routers import reports, review, timeline

ROOT = Path(__file__).resolve().parents[2]
WEB_MOCK_DIR = ROOT / "web" / "src" / "api" / "mock"

PER_PERSON_KEYS = ("question_rate", "message_length_median", "reply_gap_median_min", "resume_delay_median_min")
BANNED = {"a", "b", "baseline_a", "baseline_b", "delta_a", "delta_b"}
WEEK = "2026-08-17"   # 월요일
COUPLE = "/api/couples/c1"


def _client(me: str) -> TestClient:
    app = FastAPI()
    for mod in (timeline, reports, review):
        app.include_router(mod.router)
    app.dependency_overrides[current_member] = lambda: me
    return TestClient(app)


def _get(me: str, path: str) -> dict:
    r = _client(me).get(COUPLE + path)
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


def test_no_partner_value_on_any_read_path(payloads):
    """표시를 안 하는 게 아니라 전송을 안 한다 — 세 경로 응답 전체를 훑는다."""
    for path, (a, b) in payloads.items():
        for payload in (a, b):
            dicts = _metric_dicts(payload)
            assert dicts, f"{path}: 지표 dict 를 못 찾음 — 탐색이 헛돌고 있다"
            for d in dicts:
                assert not BANNED & set(d), f"{path}: {d}"
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
