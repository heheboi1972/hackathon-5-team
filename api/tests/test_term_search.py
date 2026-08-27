"""TASKS 3-1b 단어 횟수 검색 순수/service 계약."""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.services.crypto import BodyCipher
from app.services.kakao_parser import tokenize
from app.services.term_search import (
    TermSearchService,
    TermSearchValidationError,
    count_in_messages,
    format_answer,
    format_top_terms_answer,
    match_tokens,
    normalize_query,
    top_terms,
)
from app.tools.count_term import count_term as count_term_tool
from app.tools.top_terms import top_terms as top_terms_tool

LEXICON = {
    "좋아": ("좋아", "pos"),
    "조아": ("좋아", "pos"),
    "좋앙": ("좋아", "pos"),
    "고마워": ("고마워", "pos"),
    "감사": ("감사", "pos"),
    "땡큐": ("땡큐", "pos"),
}


def test_exact_prefix_and_canonical_modes_are_distinct():
    tokens = tokenize("사랑해 사랑해요 사랑 사랑한다", strip_particles=False)
    assert match_tokens(tokens, "사랑해", mode="exact") == ["사랑해"]
    assert match_tokens(tokens, "사랑", mode="prefix") == tokens
    variants = tokenize("좋아 조아 좋앙", strip_particles=False)
    assert sorted(match_tokens(variants, "좋아", mode="canonical", lexicon=LEXICON)) == [
        "조아", "좋아", "좋앙"
    ]
    assert normalize_query("사랑해요", strip_particles=False) == "사랑해요"


def test_canonical_does_not_merge_synonyms_or_other_sentiments():
    tokens = tokenize("고마워 감사 땡큐", strip_particles=False)
    for query in ("고마워", "감사", "땡큐"):
        result = count_in_messages(
            [(date(2026, 8, 17), tokens)], query, mode="canonical", lexicon=LEXICON
        )
        assert result["count"] == 1


def test_result_is_couple_total_and_has_no_speaker_dimension():
    messages = [
        (date(2026, 8, 17), ["사랑해", "사랑해"]),
        (date(2026, 8, 17), ["사랑해"]),
    ]
    result = count_in_messages(messages, "사랑해", mode="exact")
    assert result["query"] == "사랑해" and result["mode"] == "exact"
    assert result["count"] == result["total"] == 3
    def has_private_key(node):
        if isinstance(node, dict):
            return bool({"a", "b", "who", "sender"} & set(node)) or any(
                has_private_key(value) for value in node.values()
            )
        if isinstance(node, list):
            return any(has_private_key(value) for value in node)
        return False

    assert not has_private_key(result)
    assert result == count_in_messages(messages, "사랑해", mode="exact")


def test_arbitrary_and_missing_words_and_answer_format():
    rows = [(date(2026, 8, 17), ["치킨", "먹자", "치킨"])]
    found = count_in_messages(rows, "치킨", mode="exact")
    assert found["count"] == 2
    assert "2번" in format_answer(found)
    assert "누가 얼마나 썼는지는 알려드리지 않아요" in format_answer(
        found, asked_about_person=True
    )
    assert "찾지 못했어요" in format_answer(
        count_in_messages(rows, "피자", mode="exact")
    )


@pytest.mark.parametrize("query", ["", "   ", "두 단어", "ㅋㅋㅋ"])
def test_invalid_query(query):
    with pytest.raises(TermSearchValidationError):
        normalize_query(query)


def test_top_terms_ranks_by_count_then_alphabetically_and_excludes():
    messages = [
        (date(2026, 8, 17), ["사랑해", "치킨", "사랑해"]),
        (date(2026, 8, 18), ["치킨", "민준아", "치킨"]),
    ]
    ranked = top_terms(messages, limit=5, exclude={"민준아"})
    assert ranked == [
        {"term": "치킨", "count": 3},
        {"term": "사랑해", "count": 2},
    ]


def test_top_terms_limit_and_empty_input():
    messages = [(date(2026, 8, 17), ["가", "나", "다"])]
    assert len(top_terms(messages, limit=2)) == 2
    assert top_terms([], limit=5) == []


def test_format_top_terms_answer():
    assert "없어요" in format_top_terms_answer({"terms": []})
    single = format_top_terms_answer({"terms": [{"term": "사랑해", "count": 7}]})
    assert "사랑해" in single and "7번" in single
    multi = format_top_terms_answer(
        {"terms": [{"term": "사랑해", "count": 7}, {"term": "치킨", "count": 3}]}
    )
    assert "사랑해" in multi and "치킨" in multi and "3번" in multi


def test_invalid_mode():
    with pytest.raises(TermSearchValidationError):
        match_tokens(["사랑해"], "사랑해", mode="contains")


class _Repository:
    def __init__(self, cipher):
        self.cipher = cipher
        self.version = 2
        self.rows = [
            {"sent_at": datetime(2026, 8, 18, tzinfo=timezone.utc),
             "body_encrypted": cipher.encrypt("사랑해 치킨").decode("ascii")},
            {"sent_at": datetime(2026, 8, 19, tzinfo=timezone.utc),
             "body_encrypted": cipher.encrypt("사랑해요 사랑해").decode("ascii")},
        ]
        self.cache = {}
        self.source_reads = 0
        self.lexicons = {}

    async def get_term_source_version(self, couple_id):
        return self.version

    async def get_term_count_cache(self, couple_id, term, **kwargs):
        return self.cache.get((couple_id, term, kwargs["source_version"]))

    async def get_term_search_source(self, couple_id, **_kwargs):
        self.source_reads += 1
        return self.version, list(self.rows)

    async def get_couple_lexicon(self, couple_id):
        return self.lexicons.get(couple_id, {})

    async def save_term_count_cache(self, couple_id, term, **kwargs):
        self.cache[(couple_id, term, kwargs["source_version"])] = kwargs["result"]

    async def invalidate_term_count_cache(self, couple_id):
        keys = [key for key in self.cache if key[0] == couple_id]
        for key in keys:
            del self.cache[key]
        return len(keys)


def test_service_cache_miss_hit_invalidation_and_tool_have_no_ai_calls():
    async def scenario():
        cipher = BodyCipher(Fernet.generate_key().decode("ascii"))
        repo = _Repository(cipher)
        service = TermSearchService(repo, cipher)
        couple_id = uuid4()

        first = await count_term_tool(couple_id, "사랑해", "exact", service=service)
        assert first["count"] == 2 and repo.source_reads == 1
        second = await service.count_term(couple_id, "사랑해", "exact")
        assert second == first and repo.source_reads == 1

        repo.rows.append({
            "sent_at": datetime(2026, 8, 20, tzinfo=timezone.utc),
            "body_encrypted": cipher.encrypt("사랑해").decode("ascii"),
        })
        repo.version += 1
        assert await repo.invalidate_term_count_cache(couple_id) == 1
        refreshed = await service.count_term(couple_id, "사랑해", "exact")
        assert refreshed["count"] == 3 and repo.source_reads == 2

        # service/tool 생성자와 호출 경로 어디에도 AIService가 없다.
        assert not hasattr(service, "ai")

    asyncio.run(scenario())


def test_service_top_terms_ranks_and_excludes_lexicon_exclude_entries():
    async def scenario():
        cipher = BodyCipher(Fernet.generate_key().decode("ascii"))
        repo = _Repository(cipher)
        couple_id = uuid4()
        # repo 기본 행: "사랑해 치킨" + "사랑해요 사랑해" (exact 토큰화라 "사랑해"/"사랑해요" 구분)
        repo.lexicons[couple_id] = {"치킨": ("치킨", "exclude")}
        service = TermSearchService(repo, cipher)

        result = await top_terms_tool(couple_id, service=service, limit=5)
        terms = {item["term"]: item["count"] for item in result["terms"]}
        assert "치킨" not in terms  # exclude로 분류된 표면형은 순위에서 빠진다
        assert terms["사랑해"] == 2
        assert terms["사랑해요"] == 1

    asyncio.run(scenario())
