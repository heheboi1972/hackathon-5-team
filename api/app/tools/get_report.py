# 역할: 리포트 조회 툴 — reports 조회 + {couple, mine} 투영 (참조: API_SPEC §8, ISSUE B3)
from __future__ import annotations

from datetime import date
from uuid import UUID

from ..models.api import Who
from ..services.postgres_service import PostgresService
from ..services.projection import build_report
from . import tracer


async def get_report(
    postgres: PostgresService, couple_id: UUID, me: Who, week_start: date
) -> dict | None:
    """→ {week_start, status, report} — 없으면 None.

    `status != "generated"` 면 `report` 는 null 이다(아직 생성 전이거나 기준선 부족). 챗봇
    report_query 는 이때 지어내지 말고 "아직 리포트가 없다"고 답해야 한다.
    `execution_trace` 는 내보내지 않는다 — 운영용이라 사용자 답변에 들어갈 값이 아니다 (NFR-005).
    """
    with tracer.start_as_current_span("tool.get_report") as span:
        span.set_attribute("couple_id", str(couple_id))
        span.set_attribute("week_start", week_start.isoformat())
        row = await postgres.get_report(couple_id, week_start)
        if row is None:
            span.set_attribute("found", False)
            return None

        span.set_attribute("found", True)
        span.set_attribute("status", row["status"])
        report = row["report"]
        return {
            "week_start": row["week_start"],
            "status": row["status"],
            "report": build_report(report, me, row["week_start"]).model_dump()
            if report
            else None,
        }


async def get_latest_report_week(postgres: PostgresService, couple_id: UUID) -> date | None:
    """가장 최근 생성된 리포트의 week_start. 챗봇 report_query가 특정 주를 못 짚었을 때
    (focus_range 없음) 기본값으로 쓴다 (TASKS 3-6)."""
    with tracer.start_as_current_span("tool.get_latest_report_week") as span:
        span.set_attribute("couple_id", str(couple_id))
        week = await postgres.get_latest_generated_week(couple_id)
        span.set_attribute("found", week is not None)
        return week
