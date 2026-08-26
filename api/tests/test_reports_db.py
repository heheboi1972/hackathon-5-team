"""실제 PostgreSQL 컬럼(report_json/jobs.total,done,failed)을 사용하는 report repository 검증."""

import asyncio
from datetime import date
import os
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, sql
from psycopg.types.json import Jsonb

from app.services.postgres_service import PostgresService

TEST_POSTGRES_DSN = os.getenv("TEST_POSTGRES_DSN")


async def _run():
    schema = f"test_reports_{uuid4().hex}"
    admin = await AsyncConnection.connect(TEST_POSTGRES_DSN)
    async with admin.transaction():
        await admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    separator = "&" if "?" in TEST_POSTGRES_DSN else "?"
    repo = PostgresService(f"{TEST_POSTGRES_DSN}{separator}options=-csearch_path%3D{schema}")
    await repo.open()
    couple, week = uuid4(), date(2026, 8, 17)
    try:
        async with repo.pool.connection() as conn:
            await conn.execute("""
                CREATE TABLE weekly_metrics (
                  couple_id uuid, week_start date, summary jsonb NOT NULL,
                  metrics jsonb NOT NULL, outliers jsonb NOT NULL DEFAULT '[]',
                  summary_hash char(64), computed_at timestamptz DEFAULT now(),
                  PRIMARY KEY(couple_id, week_start))""")
            await conn.execute("""
                CREATE TABLE reports (
                  couple_id uuid, week_start date, status text NOT NULL,
                  report_json jsonb NOT NULL DEFAULT '{}', summary_hash char(64),
                  generated_at timestamptz, PRIMARY KEY(couple_id, week_start))""")
            await conn.execute("""
                CREATE TABLE weekly_terms (
                  couple_id uuid, week_start date, sender char(1), canonical text,
                  sentiment text, count int, PRIMARY KEY(couple_id,week_start,sender,canonical))""")
            await conn.execute("""
                CREATE TABLE jobs (
                  job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), couple_id uuid,
                  kind text, status text, total int DEFAULT 0,
                  done int DEFAULT 0, failed int DEFAULT 0,
                  current_week date, payload jsonb DEFAULT '{}', error text,
                  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now())""")
            await conn.execute(
                "INSERT INTO weekly_metrics VALUES (%s,%s,%s,%s,'[]',%s,now())",
                (couple, week, Jsonb({"message_count": 1}),
                 Jsonb({"question_rate": {"comparable": False}}), "a" * 64))
            await conn.execute(
                "INSERT INTO weekly_terms VALUES (%s,%s,'a','좋아','pos',4),"
                "(%s,%s,'b','고마워','pos',5)",
                (couple, week, couple, week))
        job_id = await repo.create_report_job(couple, week)
        claimed = await repo.claim_next_job(("report_single",))
        assert claimed["job_id"] == job_id and claimed["payload"]["weeks"] == [str(week)]
        rows = await repo.get_report_job_weeks(claimed)
        assert [row["week_start"] for row in rows] == [week]
        report = {"status": "insufficient_baseline", "summary": {"message_count": 1},
                  "metrics": {}, "weekly_terms": {}, "highlights": [], "suggestions": [],
                  "moments": [], "safety": None, "trace_id": "trace-1",
                  "execution_trace": [{"step": "persist", "status": "ok"}]}
        await repo.save_report(couple, week, "insufficient_baseline", report, "a" * 64)
        async with repo.pool.connection() as conn:
            first_generated_at = (await (await conn.execute(
                "SELECT generated_at FROM reports WHERE couple_id=%s AND week_start=%s",
                (couple, week))).fetchone())[0]
        await asyncio.sleep(0.01)
        await repo.save_report(couple, week, "insufficient_baseline", report, "a" * 64)
        async with repo.pool.connection() as conn:
            second_generated_at = (await (await conn.execute(
                "SELECT generated_at FROM reports WHERE couple_id=%s AND week_start=%s",
                (couple, week))).fetchone())[0]
        assert second_generated_at > first_generated_at
        loaded = await repo.get_report_record(couple, week)
        assert loaded["status"] == "insufficient_baseline"
        assert loaded["trace_id"] == "trace-1"
        assert loaded["weekly_terms"]["a"]["pos"][0]["canonical"] == "좋아"
        assert loaded["weekly_terms"]["b"]["pos"][0]["canonical"] == "고마워"
    finally:
        await repo.close()
        async with admin.transaction():
            await admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        await admin.close()


@pytest.mark.skipif(not TEST_POSTGRES_DSN, reason="TEST_POSTGRES_DSN 미설정")
def test_report_repository_against_actual_postgres_columns():
    asyncio.run(_run())
