"""실제 PostgreSQL repository를 통과하는 Timeline 읽기 경로 검증."""

import asyncio
from copy import deepcopy
from datetime import date, timedelta
import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from psycopg import AsyncConnection, sql
from psycopg.types.json import Jsonb

from app.deps import current_member
from app.routers import timeline
from app.services.postgres_service import PostgresService

TEST_POSTGRES_DSN = os.getenv("TEST_POSTGRES_DSN")
PER_PERSON_KEYS = (
    "question_rate",
    "message_length_median",
    "reply_gap_median_min",
    "resume_delay_median_min",
)
PRIVATE_KEYS = {"a", "b", "baseline_a", "baseline_b", "delta_a", "delta_b"}


def _summary(message_count: int) -> dict:
    def axes(couple, a, b):
        return {"couple": couple, "a": a, "b": b}

    return {
        "session_count": 3,
        "message_count": message_count,
        "question_rate": axes(0.5, 0.4, 0.6),
        "message_length_median": axes(12, 10, 14),
        "reply_gap_median_min": axes(5, 4, 6),
        "resume_delay_median_min": axes(100, 90, 110),
        "session_length_median": 20,
        "activity": {
            "top_weekday": 1,
            "top_hour": 21,
            "by_weekday": [0, 5, 0, 0, 0, 0, 0],
            "by_hour": [0] * 21 + [5, 0, 0],
        },
    }


def _assert_private_axes_absent(node) -> None:
    if isinstance(node, dict):
        assert not PRIVATE_KEYS & set(node), node
        for value in node.values():
            _assert_private_axes_absent(value)
    elif isinstance(node, list):
        for value in node:
            _assert_private_axes_absent(value)


async def _request(app: FastAPI, path: str) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def _run_db_test() -> None:
    schema = f"test_timeline_{uuid4().hex}"
    admin = await AsyncConnection.connect(TEST_POSTGRES_DSN)
    async with admin.transaction():
        await admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    separator = "&" if "?" in TEST_POSTGRES_DSN else "?"
    repository = PostgresService(
        f"{TEST_POSTGRES_DSN}{separator}options=-csearch_path%3D{schema}"
    )
    await repository.open()
    couple_id, other_couple_id = uuid4(), uuid4()
    weeks = [date(2026, 8, 10), date(2026, 8, 17), date(2026, 8, 24)]

    try:
        async with repository.pool.connection() as conn, conn.transaction():
            await conn.execute(
                """
                CREATE TABLE weekly_metrics (
                    couple_id UUID NOT NULL,
                    week_start DATE NOT NULL,
                    summary JSONB NOT NULL,
                    summary_hash VARCHAR(64) NOT NULL,
                    outliers JSONB NOT NULL DEFAULT '[]',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (couple_id, week_start)
                )
                """,
            )
            await conn.execute(
                """
                CREATE TABLE reports (
                    couple_id UUID NOT NULL,
                    week_start DATE NOT NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'pending',
                    report JSONB,
                    execution_trace JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (couple_id, week_start)
                )
                """,
            )
            await conn.execute(
                """
                CREATE TABLE weekly_terms (
                    couple_id UUID NOT NULL,
                    week_start DATE NOT NULL,
                    sender CHAR(1) NOT NULL,
                    canonical VARCHAR(50) NOT NULL,
                    sentiment VARCHAR(7) NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (couple_id, week_start, sender, canonical)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE events (
                    event_id BIGSERIAL PRIMARY KEY,
                    couple_id UUID NOT NULL,
                    at DATE NOT NULL,
                    kind VARCHAR(30) NOT NULL,
                    label VARCHAR(100) NOT NULL
                )
                """
            )
            for index, week_start in enumerate(reversed(weeks)):
                await conn.execute(
                    """
                    INSERT INTO weekly_metrics
                        (couple_id, week_start, summary, summary_hash, outliers)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        couple_id,
                        week_start,
                        Jsonb(_summary(100 + index)),
                        str(index) * 64,
                        Jsonb([{"metric": "reply_gap"}]) if index == 0 else Jsonb([]),
                    ),
                )
            await conn.execute(
                """
                INSERT INTO weekly_metrics
                    (couple_id, week_start, summary, summary_hash, outliers)
                VALUES (%s, %s, %s, %s, '[]')
                """,
                (other_couple_id, weeks[-1], Jsonb(_summary(999)), "x" * 64),
            )
            await conn.execute(
                """
                INSERT INTO reports (couple_id, week_start, status)
                VALUES (%s, %s, 'generated'), (%s, %s, 'failed')
                """,
                (couple_id, weeks[0], couple_id, weeks[1]),
            )
            await conn.execute(
                """
                INSERT INTO weekly_terms
                    (couple_id, week_start, sender, canonical, sentiment, count)
                VALUES
                    (%s, %s, 'a', '좋아', 'pos', 5),
                    (%s, %s, 'b', '고마워', 'pos', 4),
                    (%s, %s, 'a', '보통', 'neutral', 9)
                """,
                (
                    couple_id, weeks[-1], couple_id, weeks[-1], couple_id, weeks[-1]
                ),
            )
            await conn.execute(
                "INSERT INTO events (couple_id, at, kind, label) VALUES (%s, %s, 'anniversary', '기념일')",
                (couple_id, weeks[-1] + timedelta(days=1)),
            )

        app = FastAPI()
        app.include_router(timeline.router)
        app.state.container = SimpleNamespace(postgres=repository)
        path = (
            f"/api/couples/{couple_id}/timeline"
            f"?from={weeks[1]}&to={weeks[-1]}"
        )

        app.dependency_overrides[current_member] = lambda: "a"
        payload_a = await _request(app, path)
        app.dependency_overrides[current_member] = lambda: "b"
        payload_b = await _request(app, path)

        assert [week["week_start"] for week in payload_a["weeks"]] == [
            weeks[1].isoformat(),
            weeks[-1].isoformat(),
        ]
        assert [week["report_status"] for week in payload_a["weeks"]] == [
            "failed",
            "pending",
        ]
        assert payload_a["weeks"][-1]["in_progress"] is True
        assert payload_a["weeks"][-1]["outlier_count"] == 1
        assert payload_a["weeks"][-1]["events"][0]["label"] == "기념일"
        for key in PER_PERSON_KEYS:
            a_value = payload_a["weeks"][-1]["summary"][key]
            b_value = payload_b["weeks"][-1]["summary"][key]
            assert a_value["couple"] == b_value["couple"]
            assert a_value["mine"] != b_value["mine"]
        assert payload_a["weeks"][-1]["summary"]["sentiment"]["pos"][0]["canonical"] == "좋아"
        assert payload_b["weeks"][-1]["summary"]["sentiment"]["pos"][0]["canonical"] == "고마워"
        assert all(week["summary"]["message_count"] != 999 for week in payload_a["weeks"])
        _assert_private_axes_absent(payload_a)
        _assert_private_axes_absent(payload_b)

        changed = deepcopy(_summary(777))
        async with repository.pool.connection() as conn:
            await conn.execute(
                "UPDATE weekly_metrics SET summary = %s WHERE couple_id = %s AND week_start = %s",
                (Jsonb(changed), couple_id, weeks[-1]),
            )
        refreshed = await _request(app, path)
        assert refreshed["weeks"][-1]["summary"]["message_count"] == 777
    finally:
        await repository.close()
        async with admin.transaction():
            await admin.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
        await admin.close()


@pytest.mark.skipif(
    not TEST_POSTGRES_DSN,
    reason="TEST_POSTGRES_DSN이 설정된 경우 실제 PostgreSQL Timeline 경로를 검증합니다",
)
def test_timeline_reads_and_refreshes_actual_postgres_rows():
    asyncio.run(_run_db_test())
