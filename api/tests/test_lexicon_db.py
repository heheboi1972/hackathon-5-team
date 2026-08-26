"""실제 PostgreSQL surface/sentiment 스키마를 통과하는 build_lexicon 테스트."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from psycopg import AsyncConnection, sql

from app.services.crypto import BodyCipher
from app.services.lexicon import BuildLexiconService
from app.services.postgres_service import PostgresService

TEST_POSTGRES_DSN = os.getenv("TEST_POSTGRES_DSN")
KST = ZoneInfo("Asia/Seoul")


class _AI:
    provider_name = "watsonx"

    async def generate_json(self, messages, **kwargs):
        terms = json.loads(messages[-1]["content"])["terms"]
        return {
            "items": [
                {
                    "term": item["term"],
                    "canonical": "좋아" if item["term"] in {"조아", "좋앙"} else item["term"],
                    "polarity": "exclude" if item["term"] == "민감이름" else "pos",
                }
                for item in terms
            ]
        }


async def _run_db_test() -> None:
    schema = f"test_lexicon_{uuid4().hex}"
    admin = await AsyncConnection.connect(TEST_POSTGRES_DSN)
    async with admin.transaction():
        await admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    separator = "&" if "?" in TEST_POSTGRES_DSN else "?"
    repository = PostgresService(
        f"{TEST_POSTGRES_DSN}{separator}options=-csearch_path%3D{schema}"
    )
    await repository.open()
    couple_id, other_id = uuid4(), uuid4()
    cipher = BodyCipher("", fallback_secret="lexicon-db-test")
    at = datetime(2026, 8, 3, 10, tzinfo=KST)

    try:
        async with repository.pool.connection() as conn, conn.transaction():
            await conn.execute(
                """
                CREATE TABLE couple_lexicon (
                    couple_id UUID NOT NULL,
                    surface TEXT NOT NULL,
                    canonical TEXT NOT NULL,
                    sentiment TEXT NOT NULL CHECK (sentiment IN ('pos','neg','neutral','exclude')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (couple_id, surface)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE weekly_terms (
                    couple_id UUID NOT NULL,
                    week_start DATE NOT NULL,
                    sender CHAR(1) NOT NULL CHECK (sender IN ('a','b')),
                    canonical TEXT NOT NULL,
                    sentiment TEXT NOT NULL CHECK (sentiment IN ('pos','neg','neutral')),
                    count INTEGER NOT NULL,
                    PRIMARY KEY (couple_id, week_start, sender, canonical)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE messages (
                    message_id BIGSERIAL PRIMARY KEY,
                    couple_id UUID NOT NULL,
                    session_id BIGINT,
                    sender CHAR(1) NOT NULL,
                    sent_at TIMESTAMPTZ NOT NULL,
                    body_encrypted TEXT NOT NULL,
                    body_hash CHAR(64) NOT NULL,
                    msg_type TEXT NOT NULL DEFAULT 'text',
                    body_len INTEGER NOT NULL,
                    is_question BOOLEAN NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO couple_lexicon
                    (couple_id, surface, canonical, sentiment)
                VALUES (%s, '기존', '보존', 'neg'),
                       (%s, '조아', '다른커플', 'neg')
                """,
                (couple_id, other_id),
            )
            bodies = [
                ("a", at, "기존 조아 좋앙 민감이름"),
                ("b", at + timedelta(minutes=1), "조아 민감이름"),
                ("b", at + timedelta(days=7), "좋앙"),
            ]
            for index, (sender, sent_at, body) in enumerate(bodies):
                await conn.execute(
                    """
                    INSERT INTO messages
                        (couple_id, session_id, sender, sent_at, body_encrypted,
                         body_len, is_question, body_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, false, %s)
                    """,
                    (
                        couple_id,
                        index + 1,
                        sender,
                        sent_at,
                        cipher.encrypt(body).decode("ascii"),
                        len(body),
                        str(index) * 64,
                    ),
                )

        stored_rows = await repository.get_stored_messages(couple_id)
        assert cipher.decrypt(stored_rows[0]["body_enc"]) == bodies[0][2]
        assert stored_rows[0]["msg_hash"] == "0" * 64
        assert await repository.get_message_hashes(couple_id) == {
            "0" * 64,
            "1" * 64,
            "2" * 64,
        }
        embedding_rows = await repository.get_messages_for_embedding(couple_id)
        assert [row["session_id"] for row in embedding_rows] == [1, 2, 3]
        assert cipher.decrypt(embedding_rows[1]["body_enc"]) == bodies[1][2]
        session_rows = await repository.get_messages_in_sessions(couple_id, [3])
        assert len(session_rows) == 1
        assert cipher.decrypt(session_rows[0]["body_enc"]) == bodies[2][2]

        result = await BuildLexiconService(
            repository, _AI(), cipher, {}
        ).run(couple_id)
        assert result["inserted"] == 3

        async with repository.pool.connection() as conn:
            lexicon_rows = await (
                await conn.execute(
                    """
                    SELECT surface, canonical, sentiment
                      FROM couple_lexicon
                     WHERE couple_id=%s ORDER BY surface
                    """,
                    (couple_id,),
                )
            ).fetchall()
            weekly_rows = await (
                await conn.execute(
                    """
                    SELECT week_start, sender, canonical, sentiment, count
                      FROM weekly_terms
                     WHERE couple_id=%s ORDER BY week_start, sender, canonical
                    """,
                    (couple_id,),
                )
            ).fetchall()
            other = await (
                await conn.execute(
                    "SELECT canonical, sentiment FROM couple_lexicon WHERE couple_id=%s AND surface='조아'",
                    (other_id,),
                )
            ).fetchone()
        assert ("기존", "보존", "neg") in lexicon_rows
        assert ("조아", "좋아", "pos") in lexicon_rows
        assert ("좋앙", "좋아", "pos") in lexicon_rows
        assert ("민감이름", "민감이름", "exclude") in lexicon_rows
        assert other == ("다른커플", "neg")
        assert weekly_rows
        assert all(row[2] != "민감이름" and row[3] != "exclude" for row in weekly_rows)

        inserted = await repository.insert_couple_lexicon(
            couple_id,
            [{"surface": "기존", "canonical": "변경금지", "sentiment": "pos"}],
        )
        assert inserted == 0
        assert (await repository.get_couple_lexicon(couple_id))["기존"] == (
            "보존",
            "neg",
        )
    finally:
        await repository.close()
        async with admin.transaction():
            await admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
        await admin.close()


@pytest.mark.skipif(
    not TEST_POSTGRES_DSN, reason="TEST_POSTGRES_DSN이 있을 때 실제 PostgreSQL 검증"
)
def test_build_lexicon_through_real_postgres_repository():
    asyncio.run(_run_db_test())
