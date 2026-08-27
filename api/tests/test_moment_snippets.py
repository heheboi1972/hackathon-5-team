from datetime import datetime, timedelta, timezone

from app.services.moment_snippets import hydrate_moment_snippets


def test_hydrates_with_nearest_decrypted_message():
    at = datetime(2026, 8, 18, 10, tzinfo=timezone.utc)
    moments = [{"session_id": 3, "at": at.isoformat(), "text": "fallback"}]
    rows = [
        {"session_id": 3, "sent_at": at - timedelta(minutes=5), "body_enc": b"far"},
        {"session_id": 3, "sent_at": at + timedelta(seconds=10), "body_enc": b"near"},
    ]

    result = hydrate_moment_snippets(moments, rows, bytes.decode)

    assert result[0]["snippet"] == "near"
    assert "snippet" not in moments[0]


def test_keeps_fallback_when_decryption_fails():
    at = datetime(2026, 8, 18, 10, tzinfo=timezone.utc)
    moments = [{"session_id": 9, "at": at.isoformat(), "text": "fallback"}]
    rows = [{"session_id": 9, "sent_at": at, "body_enc": b"bad"}]

    def fail(_: bytes) -> str:
        raise ValueError("bad key")

    assert hydrate_moment_snippets(moments, rows, fail) == moments
