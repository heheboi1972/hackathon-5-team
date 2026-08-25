# 역할: 지표 조회 툴 — weekly_metrics 조회 + 기준선 계산 + {couple, mine} 투영 (참조: API_SPEC §8, ISSUE B3)
#
# 투영을 이 안에서 한다: 챗봇 metric_query 의 답은 사용자에게 그대로 나가므로 상대 값이
# 툴 밖으로 새면 안 된다. 라우터가 build_* 만 부르는 것과 같은 이유로, 툴도 저장형을 그대로 넘기지 않는다.
from __future__ import annotations

from datetime import date
from uuid import UUID

from ..models.api import Who
from ..services.metrics import metrics_from_stored
from ..services.postgres_service import PostgresService
from ..services.projection import project_metrics, project_summary
from . import tracer


async def get_metrics(
    postgres: PostgresService,
    couple_id: UUID,
    me: Who,
    *,
    week_start: date | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """→ [{week_start, summary, metrics}] 주 오름차순.

    `week_start` 는 한 주만, `start`/`end` 는 구간. 둘 다 없으면 전 주차.
    기준선은 대상 주 **직전 4주**로 계산하므로, 범위를 좁혀 요청해도 그 앞 주차까지 읽어서 계산한다
    (안 그러면 구간 첫 주가 늘 `comparable: false` 로 나온다).

    `summary.sentiment` 는 항상 null 이다 — "내 단어"는 weekly_terms 에서 오고 이 툴은 지표만 본다.
    """
    with tracer.start_as_current_span("tool.get_metrics") as span:
        span.set_attribute("couple_id", str(couple_id))
        rows = await postgres.get_weekly_metrics(couple_id, end=week_start or end)
        by_week = {row["week_start"]: row for row in rows}

        if week_start is not None:
            targets = [week_start] if week_start in by_week else []
        else:
            targets = [
                w for w in by_week
                if (start is None or w >= start) and (end is None or w <= end)
            ]

        ordered = sorted(by_week)
        out = []
        for target in sorted(targets):
            history = ordered[: ordered.index(target) + 1]
            summaries = [by_week[w]["summary"] for w in history]
            out.append({
                "week_start": target,
                "summary": project_summary(by_week[target]["summary"], me),
                "metrics": project_metrics(metrics_from_stored(summaries), me),
            })

        span.set_attribute("weeks", len(out))
        return out
