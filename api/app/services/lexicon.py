"""커플별 감성 단어 사전을 append-only로 확장하고 주차 집계를 재생성한다."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from .ai_service import AIService
from .crypto import BodyCipher
from .kakao_parser import tokenize
from .metrics import week_start_of
from .postgres_service import PostgresService

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 500
BATCH_SIZE = 100
MAX_CONTEXTS = 3
CONTEXT_WINDOW = 3
VALID_SENTIMENTS = {"pos", "neg", "neutral", "exclude"}
STORED_SENTIMENTS = {"pos", "neg", "neutral"}
_NEGATORS = {"안", "못", "별로", "전혀"}
_NEG_SUFFIXES = ("지않", "지마", "지않아", "지마라")
_MOCK_POSITIVE = {"땡큐"}
_MOCK_EXCLUDE = {
    "개새끼",
    "비밀번호",
    "시발",
    "씨발",
    "이메일",
    "전화번호",
    "주민번호",
}
_PII_PATTERN = re.compile(r"(?:\d{2,}|@)")


@dataclass(frozen=True)
class TokenMessage:
    sender: str
    sent_at: datetime
    tokens: tuple[str, ...]


def messages_from_rows(rows: list[dict[str, Any]], cipher: BodyCipher) -> list[TokenMessage]:
    """DB 암호문은 이 함수에서만 복호화하고 토큰 외 원문은 보관하지 않는다."""
    messages: list[TokenMessage] = []
    for row in rows:
        if not row["body_len"]:
            continue
        tokens = tuple(tokenize(cipher.decrypt(row["body_enc"])))
        if tokens:
            messages.append(
                TokenMessage(
                    sender=row["sender"], sent_at=row["sent_at"], tokens=tokens
                )
            )
    return sorted(messages, key=lambda message: message.sent_at)


def build_candidates(
    messages: list[TokenMessage],
    classified_surfaces: set[str],
    *,
    limit: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """전체 빈도 상위 surface에서 기존 분류를 빼고 최초 문맥 3건을 만든다."""
    counts = Counter(token for message in messages for token in message.tokens)
    ranked = sorted(counts, key=lambda surface: (-counts[surface], surface))[:limit]
    targets = [surface for surface in ranked if surface not in classified_surfaces]
    contexts: dict[str, list[str]] = {surface: [] for surface in targets}
    target_set = set(targets)

    for message in messages:
        seen_in_message: set[str] = set()
        for index, surface in enumerate(message.tokens):
            if surface not in target_set or surface in seen_in_message:
                continue
            seen_in_message.add(surface)
            examples = contexts[surface]
            if len(examples) >= MAX_CONTEXTS:
                continue
            start = max(0, index - CONTEXT_WINDOW)
            end = min(len(message.tokens), index + CONTEXT_WINDOW + 1)
            examples.append(" ".join(message.tokens[start:end]))

    return [
        {"surface": surface, "count": counts[surface], "examples": contexts[surface]}
        for surface in targets
    ]


def _is_negated(tokens: tuple[str, ...], index: int) -> bool:
    if any(token in _NEGATORS for token in tokens[max(0, index - 2) : index]):
        return True
    suffix = "".join(tokens[index + 1 : index + 3])
    return suffix.startswith(_NEG_SUFFIXES)


def aggregate_weekly_terms(
    messages: list[TokenMessage],
    lexicon: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    """시드+커플 사전을 canonical 단위로 집계한다. exclude는 결과에 없다."""
    counts: Counter[tuple[Any, str, str]] = Counter()
    sentiments: dict[tuple[Any, str, str], str] = {}
    canonical_sentiments: dict[str, str] = {}
    for message in messages:
        for index, surface in enumerate(message.tokens):
            hit = lexicon.get(surface)
            if hit is None:
                continue
            canonical, sentiment = hit
            if sentiment not in STORED_SENTIMENTS or _is_negated(message.tokens, index):
                continue
            previous = canonical_sentiments.setdefault(canonical, sentiment)
            if previous != sentiment:
                logger.warning(
                    "canonical sentiment 충돌을 제외합니다: canonical=%s %s/%s",
                    canonical,
                    previous,
                    sentiment,
                )
                continue
            key = (week_start_of(message.sent_at.date()), message.sender, canonical)
            sentiments[key] = sentiment
            counts[key] += 1
    return [
        {
            "week_start": week_start,
            "sender": sender,
            "canonical": canonical,
            "sentiment": sentiments[(week_start, sender, canonical)],
            "count": count,
        }
        for (week_start, sender, canonical), count in sorted(counts.items())
    ]


def _valid_results(
    raw: Any, candidates: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """기존 term/polarity LLM 계약을 surface/sentiment 저장 계약으로 매핑한다."""
    items = raw.get("items", raw.get("results", [])) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    requested = {candidate["surface"] for candidate in candidates}
    accepted: dict[str, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        surface = item.get("surface", item.get("term"))
        canonical = item.get("canonical")
        sentiment = item.get("sentiment", item.get("polarity"))
        if not all(isinstance(value, str) for value in (surface, canonical, sentiment)):
            continue
        surface, canonical, sentiment = surface.strip(), canonical.strip(), sentiment.strip()
        if (
            surface not in requested
            or not canonical
            or sentiment not in VALID_SENTIMENTS
            or surface in accepted
        ):
            continue
        accepted[surface] = {
            "surface": surface,
            "canonical": canonical,
            "sentiment": sentiment,
        }
    return [accepted[candidate["surface"]] for candidate in candidates if candidate["surface"] in accepted]


def _mock_results(
    candidates: list[dict[str, Any]], seed: dict[str, tuple[str, str]]
) -> list[dict[str, str]]:
    """AI_PROVIDER=mock에서 입력에만 의존하는 결정론적 분류기."""
    results: list[dict[str, str]] = []
    for candidate in candidates:
        surface = candidate["surface"]
        if surface in seed:
            canonical, sentiment = seed[surface]
        elif surface in _MOCK_POSITIVE:
            canonical, sentiment = surface, "pos"
        elif (
            surface in _MOCK_EXCLUDE
            or _PII_PATTERN.search(surface)
            or surface.endswith(("님", "씨"))
        ):
            canonical, sentiment = surface, "exclude"
        else:
            canonical, sentiment = surface, "neutral"
        results.append(
            {"surface": surface, "canonical": canonical, "sentiment": sentiment}
        )
    return results


class BuildLexiconService:
    def __init__(
        self,
        postgres: PostgresService,
        ai: AIService,
        cipher: BodyCipher,
        seed_lexicon: dict[str, tuple[str, str]],
    ):
        self.postgres = postgres
        self.ai = ai
        self.cipher = cipher
        self.seed_lexicon = dict(seed_lexicon)

    async def _classify(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        if self.ai.provider_name == "mock":
            return _mock_results(candidates, self.seed_lexicon)
        payload = {
            "terms": [
                {
                    "term": candidate["surface"],
                    "count": candidate["count"],
                    "examples": candidate["examples"],
                }
                for candidate in candidates
            ]
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "TASK:LEXICON\n"
                    "철자 변형만 같은 canonical로 묶고 동의어는 합치지 마세요. "
                    "욕설·이름·식별정보는 exclude입니다. "
                    "JSON {items:[{term,canonical,polarity}]}만 반환하고 "
                    "polarity는 pos|neg|neutral|exclude 중 하나여야 합니다."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        raw = await self.ai.generate_json(messages, max_tokens=4000, mock_key="lexicon")
        return _valid_results(raw, candidates)

    async def run(self, couple_id: UUID) -> dict[str, int]:
        stored_rows = await self.postgres.get_stored_messages(couple_id)
        messages = messages_from_rows(stored_rows, self.cipher)
        existing = await self.postgres.get_couple_lexicon(couple_id)
        candidates = build_candidates(messages, set(existing))

        classified: list[dict[str, str]] = []
        failed_batches = 0
        for start in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[start : start + BATCH_SIZE]
            try:
                results = await self._classify(batch)
                classified.extend(results)
                if len(results) != len(batch):
                    failed_batches += 1
                    logger.warning(
                        "lexicon 분류 결과 누락: couple_id=%s start=%d expected=%d actual=%d",
                        couple_id,
                        start,
                        len(batch),
                        len(results),
                    )
            except Exception:
                failed_batches += 1
                logger.exception(
                    "lexicon 분류 배치 실패: couple_id=%s start=%d", couple_id, start
                )

        inserted = await self.postgres.insert_couple_lexicon(couple_id, classified)

        # 분류 중 업로드되거나 다른 워커가 먼저 INSERT한 경우까지 최신 상태로 재집계한다.
        stored_rows = await self.postgres.get_stored_messages(couple_id)
        messages = messages_from_rows(stored_rows, self.cipher)
        effective = dict(self.seed_lexicon)
        effective.update(await self.postgres.get_couple_lexicon(couple_id))
        term_rows = aggregate_weekly_terms(messages, effective)
        await self.postgres.replace_weekly_terms(couple_id, term_rows)

        return {
            "candidates": len(candidates),
            "classified": len(classified),
            "inserted": inserted,
            "failed_batches": failed_batches,
            "weeks": len({row["week_start"] for row in term_rows}),
            "weekly_terms": len(term_rows),
        }

    async def handle_job(self, job: dict[str, Any]) -> None:
        result = await self.run(job["couple_id"])
        if result["failed_batches"]:
            raise RuntimeError(
                f"lexicon 분류 {result['failed_batches']}개 배치 실패; 시드 집계는 완료됨"
            )
        await self.postgres.update_job_progress(
            job["job_id"], done=1, failed=0, current_week=None
        )
