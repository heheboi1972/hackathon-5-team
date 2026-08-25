"""실제 PostgreSQL term_count_cache/messages/couple_lexicon 경로 검증."""

import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from psycopg import AsyncConnection, sql

from app.services.crypto import BodyCipher
from app.services.postgres_service import PostgresService
from app.services.term_search import TermSearchService

TEST_POSTGRES_DSN = os.getenv("TEST_POSTGRES_DSN")


async def _run():
    schema = f"test_term_search_{uuid4().hex}"
    admin = await AsyncConnection.connect(TEST_POSTGRES_DSN)
    async with admin.transaction():
        await admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    separator = "&" if "?" in TEST_POSTGRES_DSN else "?"
    repo = PostgresService(
        f"{TEST_POSTGRES_DSN}{separator}options=-csearch_path%3D{schema}"
    )
    await repo.open()
    cipher = BodyCipher(Fernet.generate_key().decode("ascii"))
    service = TermSearchService(repo, cipher)
    couple, other = uuid4(), uuid4()
    try:
        async with repo.pool.connection() as conn:
            await conn.execute("""
                CREATE TABLE messages (
                  message_id bigserial PRIMARY KEY, couple_id uuid NOT NULL,
                  sent_at timestamptz NOT NULL, body_encrypted text NOT NULL,
                  msg_type text NOT NULL DEFAULT 'text')""")
            await conn.execute("""
                CREATE TABLE couple_lexicon (
                  couple_id uuid NOT NULL, surface text NOT NULL, canonical text NOT NULL,
                  sentiment text NOT NULL, PRIMARY KEY(couple_id, surface))""")
            await conn.execute("""
                CREATE TABLE term_count_cache (
                  cache_id bigserial PRIMARY KEY, couple_id uuid NOT NULL, term text NOT NULL,
                  range_start timestamptz, range_end timestamptz, result jsonb NOT NULL,
                  source_version bigint NOT NULL DEFAULT 0, created_at timestamptz DEFAULT now())""")
            await conn.execute("""
                CREATE UNIQUE INDEX term_count_cache_lookup_idx ON term_count_cache
                (couple_id, term, coalesce(range_start, '-infinity'::timestamptz),
                 coalesce(range_end, 'infinity'::timestamptz))""")
            rows = [
                (couple, "조아 좋앙 사랑해 사랑해요"),
                (couple, "사랑해 치킨"),
                (other, "사랑해 사랑해 사랑해"),
            ]
            for index, (couple_id, body) in enumerate(rows):
                await conn.execute(
                    "INSERT INTO messages (couple_id,sent_at,body_encrypted) VALUES (%s,%s,%s)",
                    (couple_id, datetime(2026, 8, 18 + index, tzinfo=timezone.utc),
                     cipher.encrypt(body).decode("ascii")))
            await conn.execute(
                "INSERT INTO couple_lexicon VALUES (%s,'조아','좋아','pos'),"
                "(%s,'좋앙','좋아','pos')",
                (couple, other))

        exact = await service.count_term(couple, "사랑해", "exact")
        prefix = await service.count_term(couple, "사랑", "prefix")
        canonical = await service.count_term(couple, "좋아", "canonical")
        assert exact["count"] == 2
        assert prefix["count"] == 3
        assert canonical["count"] == 1  # 다른 couple의 좋앙 lexicon은 사용하지 않는다.
        assert await service.count_term(couple, "치킨", "exact") == await service.count_term(
            couple, "치킨", "exact")
        async with repo.pool.connection() as conn:
            cached = (await (await conn.execute(
                "SELECT count(*) FROM term_count_cache WHERE couple_id=%s", (couple,)
            )).fetchone())[0]
        assert cached == 4

        async with repo.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO messages (couple_id,sent_at,body_encrypted) VALUES (%s,%s,%s)",
                (couple, datetime(2026, 8, 21, tzinfo=timezone.utc),
                 cipher.encrypt("치킨").decode("ascii")))
        # source_version도 stale cache 사용을 막고, upload 연결은 명시적 DELETE를 수행한다.
        assert (await service.count_term(couple, "치킨", "exact"))["count"] == 2
        assert await repo.invalidate_term_count_cache(couple) == 4
    finally:
        await repo.close()
        async with admin.transaction():
            await admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        await admin.close()


@pytest.mark.skipif(not TEST_POSTGRES_DSN, reason="TEST_POSTGRES_DSN 미설정")
def test_term_search_actual_postgres_path():
    asyncio.run(_run())
