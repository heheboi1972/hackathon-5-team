"""Phase 2 백엔드 서비스의 DB 비의존 회귀 테스트."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from app.routers.upload import _message_hash, _resolve_name_map, _week_payloads
from app.services.auth import (
    InvalidToken,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)
from app.services.crypto import BodyCipher
from app.services.jobs import JobService
from app.services.kakao_parser import Message, tokenize

KST = ZoneInfo("Asia/Seoul")


def _message(sender: str, at: datetime, body: str) -> Message:
    return Message(
        sender=sender,
        sent_at=at,
        body=body,
        msg_type="text",
        is_question=body.endswith("?"),
        body_len=len(body),
        tokens=tokenize(body),
    )


def test_password_and_jwt_round_trip():
    user_id = uuid4()
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)

    token = issue_token(user_id, "test-secret", 5)
    assert decode_token(token, "test-secret") == user_id
    with pytest.raises(InvalidToken):
        decode_token(token, "other-secret")


def test_body_cipher_never_stores_plaintext_and_rejects_wrong_key():
    cipher = BodyCipher("", fallback_secret="local-one")
    encrypted = cipher.encrypt("둘만의 대화")
    assert "둘만의 대화".encode() not in encrypted
    assert cipher.decrypt(encrypted) == "둘만의 대화"
    with pytest.raises(ValueError):
        BodyCipher("", fallback_secret="local-two").decrypt(encrypted)


def test_name_map_requires_exact_detected_senders():
    assert _resolve_name_map('{"a":"윤석","b":"파트너"}', {"윤석", "파트너"}, None) == {
        "a": "윤석",
        "b": "파트너",
    }
    assert (
        _resolve_name_map(None, {"윤석", "파트너"}, {"a": "윤석", "b": "파트너"})["a"]
        == "윤석"
    )
    with pytest.raises(ValueError):
        _resolve_name_map('{"a":"윤석","b":"다른사람"}', {"윤석", "파트너"}, None)


def test_message_hash_normalizes_seconds_but_keeps_sender_and_body():
    first = _message("a", datetime(2026, 8, 24, 20, 1, 2, tzinfo=KST), "안녕")
    same_minute = _message("a", datetime(2026, 8, 24, 20, 1, 58, tzinfo=KST), "안녕")
    other_sender = _message("b", same_minute.sent_at, "안녕")
    assert _message_hash(first) == _message_hash(same_minute)
    assert _message_hash(first) != _message_hash(other_sender)


def test_week_payload_keeps_storage_axes_and_summary_excludes_baselines():
    messages = [
        _message("a", datetime(2026, 8, 24, 20, 0, tzinfo=KST), "좋아?"),
        _message("b", datetime(2026, 8, 24, 20, 2, tzinfo=KST), "좋아"),
    ]
    sessions, weeks = _week_payloads(messages, 30, {"좋아": ("좋아", "pos")})
    assert len(sessions) == 1 and len(weeks) == 1
    question = weeks[0]["summary"]["question_rate"]
    assert set(question) == {"couple", "a", "b"}
    assert not any(key.startswith("baseline_") for key in question)
    assert weeks[0]["summary_hash"]


class _FakeJobsRepo:
    def __init__(self):
        self.job = {"job_id": UUID(int=1), "kind": "demo"}
        self.finished = asyncio.Event()
        self.recovered = False

    async def recover_running_jobs(self):
        self.recovered = True
        return 1

    async def claim_next_job(self, kinds):
        if self.job and "demo" in kinds:
            job, self.job = self.job, None
            return job
        return None

    async def finish_job(self, job_id, *, error=None):
        assert job_id == UUID(int=1) and error is None
        self.finished.set()


def test_job_worker_recovers_and_dispatches_registered_handler():
    async def scenario():
        repo = _FakeJobsRepo()
        service = JobService(repo, poll_interval=0.01)
        handled = []

        async def handler(job):
            handled.append(job["job_id"])

        service.register("demo", handler)
        await service.start()
        await asyncio.wait_for(repo.finished.wait(), timeout=1)
        await service.stop()
        assert repo.recovered and handled == [UUID(int=1)]

    asyncio.run(scenario())
