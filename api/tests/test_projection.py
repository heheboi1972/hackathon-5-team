# 역할: 저장형 → 응답형 투영 테스트 — 상대 값 미전송 계약 (ISSUE B3, TC-API-005-x)
from app.services.projection import project_metrics, project_summary, strip_who

STORED_SUMMARY = {
    "session_count": 18,
    "message_count": 412,
    "question_rate": {"couple": 0.20, "a": 0.18, "b": 0.22},
    "message_length_median": {"couple": 12, "a": 14, "b": 11},
    "reply_gap_median_min": {"couple": 5, "a": 4, "b": 6},
    "resume_delay_median_min": {"couple": 118, "a": 95, "b": 140},
    "session_length_median": 22,
    "activity": {"top_weekday": 2, "top_hour": 21, "by_weekday": [0] * 7, "by_hour": [0] * 24},
}

STORED_METRICS = {
    "question_rate": {
        "couple": 0.20, "a": 0.18, "b": 0.22,
        "baseline_couple": 0.245, "baseline_a": 0.25, "baseline_b": 0.24,
        "delta_couple": -0.045, "delta_a": -0.07, "delta_b": -0.02,
        "comparable": True,
    }
}

PER_PERSON_KEYS = ("question_rate", "message_length_median", "reply_gap_median_min", "resume_delay_median_min")


def test_summary_projection_keeps_couple_and_own_value_only():
    a = project_summary(STORED_SUMMARY, "a", my_terms=None)
    b = project_summary(STORED_SUMMARY, "b", my_terms=None)
    assert a["question_rate"] == {"couple": 0.20, "mine": 0.18}
    assert b["question_rate"] == {"couple": 0.20, "mine": 0.22}
    for key in PER_PERSON_KEYS:
        # 상대 값은 표시를 안 하는 것이 아니라 응답에 담기지 않는다 (P-3 예외)
        assert "a" not in a[key] and "b" not in a[key]
        assert "a" not in b[key] and "b" not in b[key]
        # 커플 값은 두 사람에게 동일
        assert a[key]["couple"] == b[key]["couple"]


def test_summary_projection_carries_own_terms_only():
    mine = {"pos": [{"canonical": "좋아", "count": 41}], "neg": []}
    assert project_summary(STORED_SUMMARY, "a", mine)["sentiment"] == mine
    assert project_summary(STORED_SUMMARY, "a", None)["sentiment"] is None   # 사전 미구축


def test_metrics_projection_maps_baseline_and_delta():
    a = project_metrics(STORED_METRICS, "a")["question_rate"]
    b = project_metrics(STORED_METRICS, "b")["question_rate"]
    assert a == {
        "couple": 0.20, "mine": 0.18,
        "baseline_couple": 0.245, "baseline_mine": 0.25,
        "delta_couple": -0.045, "delta_mine": -0.07,
        "comparable": True,
    }
    assert b["mine"] == 0.22 and b["delta_mine"] == -0.02
    assert a["couple"] == b["couple"] and a["delta_couple"] == b["delta_couple"]
    for key in ("a", "b", "baseline_a", "baseline_b", "delta_a", "delta_b"):
        assert key not in a and key not in b


def test_strip_who_drops_speaker_but_keeps_judgement_inputs():
    """이상치 판정은 사람별 분포로 계속하고(정확도), 응답에서 who 만 뻐다."""
    stored = [{"metric": "reply_gap", "who": "b", "session_id": 1187, "value_min": 184,
               "baseline_median_min": 5, "direction": "high"}]
    out = strip_who(stored)
    assert "who" not in out[0]
    assert out[0]["value_min"] == 184 and out[0]["direction"] == "high"
    assert stored[0]["who"] == "b"   # 원본(weekly_metrics.outliers)은 그대로
