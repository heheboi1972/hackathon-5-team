"""암호화된 대화 본문에서 커플 합산 단어 횟수를 결정론적으로 계산한다."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from .crypto import BodyCipher
from .kakao_parser import tokenize
from .postgres_service import PostgresService

SearchMode = Literal["exact", "prefix", "canonical"]
VALID_MODES = {"exact", "prefix", "canonical"}
MAX_MATCHED_FORMS = 5
MAX_QUERY_LENGTH = 40
KST = ZoneInfo("Asia/Seoul")


class TermSearchValidationError(ValueError):
    pass


def normalize_query(query: str, *, strip_particles: bool = True) -> str:
    if not isinstance(query, str) or not query.strip():
        raise TermSearchValidationError("query는 비어 있을 수 없습니다")
    tokens = tokenize(query, strip_particles=strip_particles)
    if len(tokens) != 1:
        raise TermSearchValidationError("query는 하나의 단어나 표현이어야 합니다")
    normalized = tokens[0]
    if len(normalized) > MAX_QUERY_LENGTH:
        raise TermSearchValidationError(f"query는 {MAX_QUERY_LENGTH}자 이하여야 합니다")
    return normalized


def validate_mode(mode: str) -> SearchMode:
    if mode not in VALID_MODES:
        raise TermSearchValidationError("mode는 exact, prefix, canonical 중 하나여야 합니다")
    return mode  # type: ignore[return-value]


def _variants(term: str, lexicon: dict[str, tuple[str, str]] | None) -> set[str]:
    if not lexicon:
        return {term}
    canonical = lexicon.get(term, (term, ""))[0]
    variants = {
        surface
        for surface, (value, _sentiment) in lexicon.items()
        if value == canonical
    }
    return variants | {term}


def match_tokens(
    tokens: list[str],
    term: str,
    *,
    mode: SearchMode = "exact",
    lexicon: dict[str, tuple[str, str]] | None = None,
) -> list[str]:
    validate_mode(mode)
    if mode == "exact":
        return [token for token in tokens if token == term]
    if mode == "prefix":
        return [token for token in tokens if token.startswith(term)]
    variants = _variants(term, lexicon)
    return [token for token in tokens if token in variants]


def count_in_messages(
    messages: list[tuple[date, list[str]]],
    query: str,
    *,
    mode: SearchMode = "exact",
    lexicon: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """sender 없는 주차별 token 목록만 받아 커플 합산 결과를 만든다."""
    validate_mode(mode)
    by_week: dict[date, int] = defaultdict(int)
    forms: dict[str, int] = defaultdict(int)
    for week_start, tokens in messages:
        for hit in match_tokens(tokens, query, mode=mode, lexicon=lexicon):
            by_week[week_start] += 1
            forms[hit] += 1
    count = sum(by_week.values())
    return {
        "query": query,
        "mode": mode,
        "count": count,
        # API_SPEC §8의 기존 tool payload와의 하위 호환 필드
        "term": query,
        "total": count,
        "matched_forms": [
            {"form": form, "count": value}
            for form, value in sorted(
                forms.items(), key=lambda item: (-item[1], item[0])
            )[:MAX_MATCHED_FORMS]
        ],
        "by_week": [
            {"week_start": week_start, "count": by_week[week_start]}
            for week_start in sorted(by_week)
        ],
    }


def format_answer(result: dict[str, Any], asked_about_person: bool = False) -> str:
    term, total = result["term"], result["total"]
    if total == 0:
        return f"'{term}'은 대화 기록에서 찾지 못했어요."
    forms = result["matched_forms"]
    detail = ""
    if len(forms) > 1:
        detail = " (" + " · ".join(
            f"{item['form']} {item['count']}" for item in forms
        ) + ")"
    answer = f"'{term}'은 전체 대화에서 {total}번 나왔어요{detail}."
    if asked_about_person:
        answer += " 누가 얼마나 썼는지는 알려드리지 않아요."
    return answer


def _week_start(value: datetime) -> date:
    local = value if value.tzinfo is None else value.astimezone(KST)
    current = local.date()
    return current - timedelta(days=current.weekday())


def _decrypt_and_tokenize(
    rows: list[dict[str, Any]], cipher: BodyCipher, mode: SearchMode
) -> list[tuple[date, list[str]]]:
    messages: list[tuple[date, list[str]]] = []
    for row in rows:
        encrypted = row["body_encrypted"]
        if isinstance(encrypted, str):
            encrypted = encrypted.encode("ascii")
        body = cipher.decrypt(encrypted)
        # exact에서 '사랑해'와 '사랑해요'를 구분하기 위해 본문은 조사 제거를 하지 않는다.
        tokens = tokenize(body, strip_particles=mode == "canonical")
        if tokens:
            messages.append((_week_start(row["sent_at"]), tokens))
    return messages


def _cache_key(query: str, mode: SearchMode) -> str:
    # 실제 cache schema에는 mode 컬럼이 없으므로 term key에서 충돌을 분리한다.
    return f"{mode}:{query}"


def _cache_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "by_week": [
            {**item, "week_start": str(item["week_start"])}
            for item in result["by_week"]
        ],
    }


def _restore_cache(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "by_week": [
            {
                **item,
                "week_start": date.fromisoformat(item["week_start"])
                if isinstance(item["week_start"], str)
                else item["week_start"],
            }
            for item in result.get("by_week", [])
        ],
    }


class TermSearchService:
    """Postgres cache와 BodyCipher를 조립하며 AI service를 의존하지 않는다."""

    def __init__(self, postgres: PostgresService, cipher: BodyCipher):
        self.postgres = postgres
        self.cipher = cipher

    async def count_term(
        self,
        couple_id: UUID,
        query: str,
        mode: str = "exact",
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        selected_mode = validate_mode(mode)
        normalized = normalize_query(
            query, strip_particles=selected_mode != "exact"
        )
        if start is not None and end is not None and end < start:
            raise TermSearchValidationError("end는 start보다 빠를 수 없습니다")
        cache_key = _cache_key(normalized, selected_mode)
        current_version = await self.postgres.get_term_source_version(couple_id)
        cached = await self.postgres.get_term_count_cache(
            couple_id,
            cache_key,
            start=start,
            end=end,
            source_version=current_version,
        )
        if cached is not None:
            return _restore_cache(cached)

        source_version, rows = await self.postgres.get_term_search_source(
            couple_id, start=start, end=end
        )
        lexicon = (
            await self.postgres.get_couple_lexicon(couple_id)
            if selected_mode == "canonical"
            else None
        )
        messages = await asyncio.to_thread(
            _decrypt_and_tokenize, rows, self.cipher, selected_mode
        )
        result = await asyncio.to_thread(
            count_in_messages,
            messages,
            normalized,
            mode=selected_mode,
            lexicon=lexicon,
        )
        await self.postgres.save_term_count_cache(
            couple_id,
            cache_key,
            start=start,
            end=end,
            source_version=source_version,
            result=_cache_payload(result),
        )
        return result
