"""TASKS 3-1a build_lexicon 순수 단위 테스트."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.services.lexicon import (
    BuildLexiconService,
    TokenMessage,
    aggregate_weekly_terms,
    build_candidates,
)

KST = ZoneInfo("Asia/Seoul")


class _PlainCipher:
    def decrypt(self, encrypted: bytes) -> str:
        return encrypted.decode("utf-8")


class _Repo:
    def __init__(self):
        self.messages = {}
        self.lexicons = {}
        self.weekly = {}
        self.progress = []

    async def get_stored_messages(self, couple_id):
        return deepcopy(self.messages.get(couple_id, []))

    async def get_couple_lexicon(self, couple_id):
        return deepcopy(self.lexicons.get(couple_id, {}))

    async def insert_couple_lexicon(self, couple_id, entries):
        target = self.lexicons.setdefault(couple_id, {})
        inserted = 0
        for entry in entries:
            if entry["surface"] not in target:
                target[entry["surface"]] = (
                    entry["canonical"],
                    entry["sentiment"],
                )
                inserted += 1
        return inserted

    async def replace_weekly_terms(self, couple_id, rows):
        self.weekly[couple_id] = deepcopy(rows)

    async def update_job_progress(self, job_id, **progress):
        self.progress.append((job_id, progress))


class _ClassifyingAI:
    provider_name = "watsonx"

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.batches = []

    async def generate_json(self, messages, **kwargs):
        if self.fail:
            raise RuntimeError("model unavailable")
        payload = json.loads(messages[-1]["content"])
        terms = payload["terms"]
        self.batches.append([term["term"] for term in terms])
        variants = {"조아": "좋아", "좋앙": "좋아"}
        positive = {"조아", "좋앙", "고마워", "감사", "땡큐"}
        return {
            "items": [
                {
                    "term": term["term"],
                    "canonical": variants.get(term["term"], term["term"]),
                    "polarity": (
                        "exclude"
                        if term["term"] == "비밀이름"
                        else "pos" if term["term"] in positive else "neutral"
                    ),
                }
                for term in terms
            ]
        }


class _MockAI:
    provider_name = "mock"

    async def generate_json(self, *args, **kwargs):  # pragma: no cover - 호출 금지 검증
        raise AssertionError("mock build_lexicon은 외부 생성 호출을 하지 않아야 한다")


def _row(sender: str, at: datetime, body: str) -> dict:
    return {
        "sender": sender,
        "sent_at": at,
        "body_enc": body.encode("utf-8"),
        "body_len": len(body),
        "is_question": False,
        "msg_hash": body,
    }


def test_candidates_are_ranked_and_keep_first_three_deterministic_contexts():
    start = datetime(2026, 8, 3, 10, tzinfo=KST)
    messages = [
        TokenMessage("a", start + timedelta(minutes=i), tuple(text.split()))
        for i, text in enumerate(
            [
                "앞 하나 조아 뒤 하나",
                "앞 둘 조아 뒤 둘",
                "앞 셋 조아 뒤 셋",
                "앞 넷 조아 뒤 넷",
                "이미 이미 조아",
            ]
        )
    ]
    candidates = build_candidates(messages, {"이미"})
    joa = next(item for item in candidates if item["surface"] == "조아")
    assert joa["count"] == 5
    assert joa["examples"] == [
        "앞 하나 조아 뒤 하나",
        "앞 둘 조아 뒤 둘",
        "앞 셋 조아 뒤 셋",
    ]
    assert "이미" not in {item["surface"] for item in candidates}


def test_build_is_append_only_maps_llm_contract_and_reaggregates():
    async def scenario():
        repo = _Repo()
        couple_id, other_id = uuid4(), uuid4()
        start = datetime(2026, 8, 3, 10, tzinfo=KST)
        repo.messages[couple_id] = [
            _row("a", start, "이미 조아 좋앙 고마워 감사 땡큐 비밀이름"),
            _row("b", start + timedelta(minutes=1), "조아 비밀이름"),
            _row("b", start + timedelta(days=7), "좋앙 고마워"),
        ]
        repo.lexicons[couple_id] = {"이미": ("보존", "neg")}
        repo.lexicons[other_id] = {"조아": ("다른커플", "neg")}
        ai = _ClassifyingAI()
        service = BuildLexiconService(repo, ai, _PlainCipher(), {})

        first = await service.run(couple_id)
        assert all("이미" not in batch for batch in ai.batches)
        assert repo.lexicons[couple_id]["이미"] == ("보존", "neg")
        assert repo.lexicons[couple_id]["조아"] == ("좋아", "pos")
        assert repo.lexicons[couple_id]["좋앙"] == ("좋아", "pos")
        assert [repo.lexicons[couple_id][term][0] for term in ("고마워", "감사", "땡큐")] == [
            "고마워",
            "감사",
            "땡큐",
        ]
        assert repo.lexicons[couple_id]["비밀이름"][1] == "exclude"
        assert all(row["canonical"] != "비밀이름" for row in repo.weekly[couple_id])
        assert {row["week_start"] for row in repo.weekly[couple_id]} == {
            start.date(),
            (start + timedelta(days=7)).date(),
        }
        assert repo.lexicons[other_id] == {"조아": ("다른커플", "neg")}
        snapshot = deepcopy(repo.lexicons[couple_id])
        call_count = len(ai.batches)

        second = await service.run(couple_id)
        assert repo.lexicons[couple_id] == snapshot
        assert len(ai.batches) == call_count
        assert first["inserted"] == 6
        assert second["inserted"] == 0

    asyncio.run(scenario())


def test_mock_classification_is_deterministic_and_does_not_merge_synonyms():
    async def scenario():
        repo = _Repo()
        couple_id = uuid4()
        at = datetime(2026, 8, 3, 10, tzinfo=KST)
        repo.messages[couple_id] = [
            _row("a", at, "조아 좋앙 고마워 감사 땡큐")
        ]
        seed = {
            "조아": ("좋아", "pos"),
            "좋앙": ("좋아", "pos"),
            "고마워": ("고마워", "pos"),
            "감사": ("감사", "pos"),
        }
        service = BuildLexiconService(repo, _MockAI(), _PlainCipher(), seed)
        result = await service.run(couple_id)
        assert result["failed_batches"] == 0
        assert repo.lexicons[couple_id]["조아"] == ("좋아", "pos")
        assert repo.lexicons[couple_id]["좋앙"] == ("좋아", "pos")
        assert [repo.lexicons[couple_id][term][0] for term in ("고마워", "감사", "땡큐")] == [
            "고마워",
            "감사",
            "땡큐",
        ]
        job_id = uuid4()
        await service.handle_job({"job_id": job_id, "couple_id": couple_id})
        assert repo.progress == [
            (job_id, {"done": 1, "failed": 0, "current_week": None})
        ]

    asyncio.run(scenario())


def test_batches_are_capped_at_one_hundred():
    async def scenario():
        repo = _Repo()
        couple_id = uuid4()
        at = datetime(2026, 8, 3, 10, tzinfo=KST)
        repo.messages[couple_id] = [
            _row("a", at, " ".join(f"단어{i:03d}" for i in range(205)))
        ]
        ai = _ClassifyingAI()
        await BuildLexiconService(repo, ai, _PlainCipher(), {}).run(couple_id)
        assert [len(batch) for batch in ai.batches] == [100, 100, 5]

    asyncio.run(scenario())


def test_seed_reaggregation_survives_llm_failure_and_keeps_negation_rule():
    async def scenario():
        repo = _Repo()
        couple_id = uuid4()
        at = datetime(2026, 8, 3, 10, tzinfo=KST)
        repo.messages[couple_id] = [
            _row("a", at, "좋아 안 좋아 좋아 지 않아 미분류")
        ]
        service = BuildLexiconService(
            repo, _ClassifyingAI(fail=True), _PlainCipher(), {"좋아": ("좋아", "pos")}
        )
        result = await service.run(couple_id)
        assert result["failed_batches"] == 1
        assert repo.weekly[couple_id] == [
            {
                "week_start": at.date(),
                "sender": "a",
                "canonical": "좋아",
                "sentiment": "pos",
                "count": 1,
            }
        ]

    asyncio.run(scenario())


def test_aggregate_never_emits_exclude():
    at = datetime(2026, 8, 3, 10, tzinfo=KST)
    messages = [TokenMessage("a", at, ("표시", "비밀"))]
    rows = aggregate_weekly_terms(
        messages, {"표시": ("표시", "neutral"), "비밀": ("비밀", "exclude")}
    )
    assert rows == [
        {
            "week_start": at.date(),
            "sender": "a",
            "canonical": "표시",
            "sentiment": "neutral",
            "count": 1,
        }
    ]
