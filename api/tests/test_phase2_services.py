"""Phase 2 백엔드 서비스의 DB 비의존 회귀 테스트."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import UploadFile

import app.routers.upload as upload_module
from app.deps import AuthenticatedUser
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
    first = _message("a", datetime(2026, 8, 24, 20, 1, 2, tzinfo=KST), "안녕\r\n")
    same_minute = _message(
        "a", datetime(2026, 8, 24, 20, 1, 58, tzinfo=KST), "안녕\n"
    )
    other_sender = _message("b", same_minute.sent_at, "안녕")
    assert _message_hash(first) == _message_hash(same_minute)
    assert _message_hash(first) != _message_hash(other_sender)
    assert _message_hash(first) != _message_hash(
        _message("a", same_minute.sent_at, "다른 본문")
    )


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
    assert set(weeks[0]["metrics"]) == {
        "question_rate", "message_length_median", "reply_gap_median_min"
    }


class _IncrementalUploadRepo:
    def __init__(self):
        self.rows: list[dict] = []
        self.updated_week_counts: list[int] = []
        self.updated_weeks: list[list[dict]] = []

    async def get_active_couple(self, couple_id, user_id):
        return {
            "member": "a",
            "status": "active",
            "kakao_name_a": "A",
            "kakao_name_b": "B",
        }

    async def get_stored_messages(self, couple_id):
        return list(self.rows)

    async def get_couple_lexicon(self, couple_id):
        return {}

    async def apply_upload(
        self,
        couple_id,
        *,
        user_id,
        base_hashes,
        kakao_names,
        new_messages,
        sessions,
        weeks,
    ):
        assert base_hashes == {row["msg_hash"] for row in self.rows}
        self.updated_week_counts.append(len(weeks))
        self.updated_weeks.append(weeks)
        self.rows.extend(new_messages)
        return {
            "embed_job_id": uuid4(),
            "report_job_id": uuid4(),
            "changed_weeks": [week["week_start"] for week in weeks],
        }


def _messages_for_weeks(count: int) -> list[Message]:
    start = datetime(2026, 1, 5, 20, tzinfo=KST)
    messages = []
    for index in range(count):
        at = start + timedelta(weeks=index)
        messages.extend(
            [
                _message("A", at, f"질문 {index}?"),
                _message("B", at + timedelta(minutes=5), f"답변 {index}"),
            ]
        )
    return messages


def test_incremental_upload_only_enqueues_weeks_with_new_messages(monkeypatch):
    async def scenario():
        base = _messages_for_weeks(25)
        batches = iter([base, base, _messages_for_weeks(26)])
        monkeypatch.setattr(
            upload_module,
            "_parse",
            lambda data: ("pc", next(batches)),
        )
        repo = _IncrementalUploadRepo()
        container = SimpleNamespace(
            postgres=repo,
            cipher=BodyCipher("", fallback_secret="incremental-upload-test"),
            knowledge=SimpleNamespace(seed_lexicon={}),
            settings=SimpleNamespace(session_gap_min=30),
        )
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(container=container))
        )
        couple_id = uuid4()
        user = AuthenticatedUser(uuid4(), "user@example.com", "사용자", couple_id, "a")

        async def call_upload():
            return await upload_module.upload(
                couple_id,
                request,
                user,
                UploadFile(file=BytesIO(b"fixture"), filename="chat.txt"),
                None,
            )

        first = await call_upload()
        # 운영 DB에 과거 hash 규칙으로 저장된 행이 있어도 현재 canonical input으로
        # 기존 메시지를 재구성해 동일 파일을 중복으로 판단해야 한다.
        for index, row in enumerate(repo.rows):
            row["msg_hash"] = f"{index:064x}"

        same = await call_upload()
        extended = await call_upload()

        assert (first.weeks_computed, first.report_jobs.total) == (25, 25)
        assert (same.weeks_computed, same.report_jobs.total) == (25, 0)
        assert same.parsed.new_messages == 0
        assert (extended.weeks_computed, extended.report_jobs.total) == (26, 1)
        assert extended.parsed.new_messages == 2
        assert repo.updated_week_counts == [25, 0, 1]

        first_weeks = repo.updated_weeks[0]
        expected_keys = {
            "question_rate", "message_length_median", "reply_gap_median_min"
        }
        assert all(set(week["metrics"]) == expected_keys for week in first_weeks)
        assert all(
            metric["comparable"] is False
            for week in first_weeks[:4]
            for metric in week["metrics"].values()
        )
        assert all(
            metric["comparable"] is True
            for metric in first_weeks[-1]["metrics"].values()
        )
        assert repo.updated_weeks[1] == []
        assert len(repo.updated_weeks[2]) == 1
        assert all(metric["comparable"] for metric in repo.updated_weeks[2][0]["metrics"].values())

    asyncio.run(scenario())


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
