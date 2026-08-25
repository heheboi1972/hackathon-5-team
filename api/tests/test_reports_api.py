"""API_SPEC §4.2/4.3 report 상태·projection 계약."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import current_member
from app.agents.safety_agent import load_banned_patterns
from app.routers import reports

COUPLE = UUID("11111111-1111-1111-1111-111111111111")
WEEK = date(2026, 8, 17)


def _axes(couple, a, b, comparable=None):
    value = {"couple": couple, "a": a, "b": b}
    if comparable is not None:
        value.update({"baseline_couple": couple + 1, "baseline_a": a + 1,
                      "baseline_b": b + 1, "delta_couple": -1,
                      "delta_a": -1, "delta_b": -1, "comparable": comparable})
    return value


SUMMARY = {
    "session_count": 3, "message_count": 40,
    "question_rate": _axes(20, 18, 22),
    "message_length_median": _axes(12, 10, 14),
    "reply_gap_median_min": _axes(5, 4, 6),
    "resume_delay_median_min": _axes(90, 80, 100),
    "session_length_median": 22,
    "activity": {"top_weekday": 1, "top_hour": 21, "by_weekday": [0] * 7,
                 "by_hour": [0] * 24},
}
METRICS = {"question_rate": _axes(20, 18, 22, True)}
TERMS = {"a": {"pos": [{"canonical": "좋아", "count": 4}], "neg": []},
         "b": {"pos": [{"canonical": "고마워", "count": 5}], "neg": []}}
TEMPLATE_IDS = {"q-down-1"}


class Repo:
    def __init__(self, stored): self.stored, self.queued = stored, []
    async def get_report_record(self, couple, week):
        return deepcopy(self.stored) if couple == COUPLE and week == WEEK else None
    async def create_report_job(self, couple, week):
        self.queued.append((couple, week))
        return UUID(int=7)


def client(stored, me="a"):
    app = FastAPI()
    app.include_router(reports.router)
    repo = Repo(stored)
    app.state.container = SimpleNamespace(postgres=repo)
    app.dependency_overrides[current_member] = lambda: me
    return TestClient(app), repo


def _stored(status):
    return {"status": status, "summary": SUMMARY,
            "metrics": {} if status == "pending" else METRICS,
            "weekly_terms": TERMS, "highlights": [], "suggestions": [],
            "moments": [], "safety": None}


def test_pending_and_insufficient_status_contracts():
    pending, _ = client(_stored("pending"))
    body = pending.get(f"/api/couples/{COUPLE}/reports/{WEEK}").json()
    assert body["status"] == "pending" and body["summary"] and body["metrics"] == {}
    insufficient, _ = client(_stored("insufficient_baseline"))
    body = insufficient.get(f"/api/couples/{COUPLE}/reports/{WEEK}").json()
    assert body["status"] == "insufficient_baseline"
    assert body["highlights"] == [] and body["suggestions"] == []


def test_generated_projection_and_content_invariants_for_a_and_b():
    stored = _stored("generated")
    stored.update({
        "highlights": [{"id": "h1", "metric": "question_rate",
                        "observation": "지난 흐름에 비해 묻는 순간이 조금 줄어들었어요",
                        "interpretations": ["바쁜 시기였을 수도", "대화 주제가 옮겨간 걸 수도"],
                        "evidence": [], "sources": [], "sentiment": "neutral"}],
        "suggestions": [{"id": "s1", "linked_highlight": "h1",
                         "template_id": "q-down-1",
                         "text": "서로 궁금했던 순간을 가볍게 나눠보면 어떨까요"}],
        "moments": [{"kind": "reply_gap", "at": "2026-08-18T10:00:00+09:00",
                     "session_id": 3, "value_min": 20, "baseline_median_min": 5,
                     "text": "평소와 다른 흐름이 포착됐어요", "who": "b"}],
        "safety": {"passed": True, "rewritten": []},
    })
    a = client(stored, "a")[0].get(f"/api/couples/{COUPLE}/reports/{WEEK}").json()
    b = client(stored, "b")[0].get(f"/api/couples/{COUPLE}/reports/{WEEK}").json()
    assert a["summary"]["question_rate"]["couple"] == b["summary"]["question_rate"]["couple"]
    assert a["summary"]["question_rate"]["mine"] != b["summary"]["question_rate"]["mine"]
    assert a["metrics"]["question_rate"]["mine"] != b["metrics"]["question_rate"]["mine"]
    assert len(a["highlights"][0]["interpretations"]) >= 2
    assert a["highlights"][0]["sentiment"] in {"positive", "neutral", "notable"}
    assert all(item["template_id"] in TEMPLATE_IDS for item in a["suggestions"])
    generated_texts = [a["highlights"][0]["observation"],
                       *a["highlights"][0]["interpretations"],
                       *(item["text"] for item in a["suggestions"])]
    assert not any(pattern.search(value) for pattern in load_banned_patterns()
                   for value in generated_texts)
    text = str(a)
    assert "'a':" not in text and "'b':" not in text and "'who':" not in text


def test_validation_not_found_and_regenerate_are_async_queue_operations():
    api, repo = client(_stored("generated"))
    assert api.get(f"/api/couples/{COUPLE}/reports/2026-08-18").status_code == 400
    assert api.get(f"/api/couples/{COUPLE}/reports/2026-08-10").status_code == 404
    response = api.post(f"/api/couples/{COUPLE}/reports/{WEEK}/regenerate")
    assert response.status_code == 202 and response.json() == {"job_id": str(UUID(int=7))}
    assert repo.queued == [(COUPLE, WEEK)]
