# 역할: 지표 조회 툴 — 챗봇 metric_query 전용 (참조: API_SPEC §8, ISSUE A7)
#
# 2026-08-25 결정(A7)으로 돌아보기(Review) 화면과 같은 range-vs-baseline 형태로 좁혔다.
# (couple_id, focus_range?) → {range, baseline, comment} — 계산·투영은 review_metrics.py/
# projection.py를 그대로 재사용한다(돌아보기와 로직 중복 방지, chat_answer.md 알려진 한계 해소).
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from ..models.api import Who
from ..services.postgres_service import PostgresService
from ..services.projection import project_metrics
from ..services.review_metrics import build_stored_review
from . import tracer

KST = timezone(timedelta(hours=9))
DEFAULT_WINDOW_DAYS = 7  # focus_range 없을 때("요즘 어때?" 류) 기본 구간 — 챗봇 전용 판단(해찬, 2026-08-26).
# review 라우터(2주 상한, start/end 필수)와 다르게 챗봇은 대화가 끊기면 안 되므로 폴백을 둔다.


async def get_metrics(
    postgres: PostgresService,
    couple_id: UUID,
    me: Who,
    *,
    focus_range: tuple[datetime, datetime] | None = None,
) -> dict:
    """→ {range: RangeMetrics 저장형, baseline: BaselineMetrics 저장형, comment: str}.

    `range`/`baseline`는 이미 `{couple, mine}`로 투영된 응답형이다 — 챗봇이 그대로
    `ChatResponse.metrics`에 실어 보낸다. LLM에는 이 값을 그대로 전달하고, 문장 생성 시
    새 숫자를 계산하지 않도록 하는 건 프롬프트(chat_answer.md) + 서버가 LLM의 echo를
    신뢰하지 않고 이 값을 직접 응답에 붙이는 것(chat_supervisor) 둘 다로 강제한다.
    """
    with tracer.start_as_current_span("tool.get_metrics") as span:
        span.set_attribute("couple_id", str(couple_id))
        if focus_range is not None:
            start, end = focus_range
        else:
            end = datetime.now(KST)
            start = end - timedelta(days=DEFAULT_WINDOW_DAYS)
        raw = await postgres.get_review_data(couple_id, start=start, end=end, session_id=None)
        stored = build_stored_review(raw, mode="date")
        span.set_attribute("comment", stored["metrics"]["comment"])
        return {
            "range": project_metrics(stored["metrics"]["range"], me),
            "baseline": project_metrics(stored["metrics"]["baseline"], me),
            "comment": stored["metrics"]["comment"],
        }
