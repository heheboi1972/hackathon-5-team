# 역할: API 요청/응답 Pydantic 모델 — web/src/api/types.ts 와 1:1 계약 (참조: docs/API_SPEC.md)
# 변경 시 팀 채널 공지 + types.ts 동기화 (SCAFFOLD §3 충돌 방지 규칙)
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Who = Literal["a", "b"]
CoupleStatus = Literal["pending", "awaiting_confirm", "active", "dissolved"]
ReportStatus = Literal["generated", "insufficient_baseline", "pending", "failed"]
JobStatus = Literal["queued", "running", "done", "failed"]
JobKind = Literal["embed_sessions", "build_lexicon", "report_backfill", "report_single"]
Intent = Literal["fact_query", "metric_query", "report_query", "term_count", "top_term", "advice_request", "other"]
Sentiment = Literal["positive", "neutral", "notable"]


# ---------------------------------------------------------------- 공통

class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class CoupleMine(BaseModel):
    """커플 합산 + 요청자 본인 값. 상대 값은 응답에 담지 않는다 (P-3 예외, ISSUE B3).
    `mine` 은 기본값이 없다(널은 허용, 키는 필수) — 저장형을 투영 없이 넣으면 여기서 터진다"""
    couple: float | None = None
    mine: float | None


# ---------------------------------------------------------------- 1. 인증 (FR-000)

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: str
    token: str
    couple_id: str | None = None
    couple_status: CoupleStatus | None = None


# ---------------------------------------------------------------- 2. 커플 연결 (FR-001)

class InviteResponse(BaseModel):
    couple_id: str
    invite_code: str
    expires_at: datetime
    status: CoupleStatus


class JoinRequest(BaseModel):
    invite_code: str


class PartnerInfo(BaseModel):
    display_name: str


class JoinResponse(BaseModel):
    couple_id: str
    status: CoupleStatus
    partner: PartnerInfo


class ConfirmRequest(BaseModel):
    accept: bool


class ConfirmResponse(BaseModel):
    couple_id: str
    status: CoupleStatus


class MemberInfo(BaseModel):
    user_id: str
    display_name: str


class CoupleMembers(BaseModel):
    a: MemberInfo
    b: MemberInfo


class CoupleData(BaseModel):
    first_week: date
    last_week: date
    weeks_available: int
    message_count: int


class ActiveJob(BaseModel):
    """진행 중인 잡 (새로고침 후 진행률 복구용). 없으면 null"""
    job_id: str
    kind: JobKind
    done: int
    total: int


class CoupleMeResponse(BaseModel):
    couple_id: str | None = None
    status: CoupleStatus | None = None
    members: CoupleMembers | None = None
    me: Who | None = None
    kakao_names: dict[Who, str] | None = None
    started_at: date | None = None
    first_met_at: date | None = None
    data: CoupleData | None = None
    active_job: ActiveJob | None = None


class CoupleSettingsUpdate(BaseModel):
    first_met_at: date | None


# ---------------------------------------------------------------- 3. 업로드 (FR-002)

class DateRange(BaseModel):
    from_: date = Field(alias="from")
    to: date

    model_config = {"populate_by_name": True}


class ParsedInfo(BaseModel):
    format: Literal["pc", "ios", "android"]
    message_count: int
    new_messages: int
    session_count: int
    range: DateRange


class ReportJobsInfo(BaseModel):
    total: int
    pending: int


class JobRef(BaseModel):
    job_id: str


class UploadResponse(BaseModel):
    job_id: str                      # 리포트 잡 (report_backfill)
    embed_job: JobRef                # 임베딩 잡 (embed_sessions) — 리포트 잡보다 먼저 실행
    parsed: ParsedInfo
    weeks_computed: int
    report_jobs: ReportJobsInfo


class JobProgress(BaseModel):
    total: int
    done: int
    failed: int


class JobResponse(BaseModel):
    job_id: str
    kind: JobKind
    status: JobStatus
    progress: JobProgress
    current_week: date | None = None


# ---------------------------------------------------------------- 4. 타임라인·리포트 (FR-003, FR-004)

class Activity(BaseModel):
    """활발한 요일·시간대 (커플 합산). 메시지 없으면 top_* null"""
    top_weekday: int | None = None   # 0=월 … 6=일
    top_hour: int | None = None      # 0~23
    by_weekday: list[int]            # 길이 7
    by_hour: list[int]               # 길이 24


class TermCount(BaseModel):
    canonical: str
    count: int


class MyTerms(BaseModel):
    """'내 단어' — 요청자 본인의 pos/neg 상위 3 (count<3 숨김). 상대 데이터는 전송하지 않음 (P-3 예외)"""
    pos: list[TermCount] = []
    neg: list[TermCount] = []


class WeekSummary(BaseModel):
    session_count: int
    message_count: int
    question_rate: CoupleMine
    message_length_median: CoupleMine
    reply_gap_median_min: CoupleMine
    resume_delay_median_min: CoupleMine
    session_length_median: float
    activity: Activity
    sentiment: MyTerms | None = None   # 사전 미구축 시 null


class TimelineWeek(BaseModel):
    week_start: date
    in_progress: bool = False
    report_status: ReportStatus
    summary: WeekSummary
    outlier_count: int = 0
    events: list[dict[str, Any]] = []


class TimelineResponse(BaseModel):
    weeks: list[TimelineWeek]


class MetricComparison(BaseModel):
    """커플 값 + 본인 값. 리포트 문장·하이라이트는 couple 기준 (ISSUE B3).
    `mine` 필수 — 이유는 `CoupleMine` 참조"""
    couple: float | None = None
    mine: float | None
    baseline_couple: float | None = None
    baseline_mine: float | None = None
    delta_couple: float | None = None
    delta_mine: float | None = None
    comparable: bool = False


class Evidence(BaseModel):
    session_id: int
    at: datetime
    snippet: str


class Source(BaseModel):
    doc: str
    section: str


class Highlight(BaseModel):
    id: str
    metric: str
    observation: str
    interpretations: list[str] = Field(min_length=2)  # 불변 규칙: 해석 ≥ 2 (API_SPEC §4.2)
    evidence: list[Evidence] = []
    sources: list[Source] = []
    sentiment: Sentiment = "neutral"


class Suggestion(BaseModel):
    id: str
    linked_highlight: str
    template_id: str
    text: str


class Moment(BaseModel):
    kind: str
    at: datetime
    session_id: int
    value_min: float | None = None
    baseline_median_min: float | None = None
    text: str
    snippet: str | None = None


class SafetyResult(BaseModel):
    passed: bool = True
    rewritten: list[dict[str, str]] = []


class ReportResponse(BaseModel):
    week_start: date
    status: ReportStatus
    summary: WeekSummary | None = None
    metrics: dict[str, MetricComparison] = {}
    highlights: list[Highlight] = []
    suggestions: list[Suggestion] = []
    moments: list[Moment] = []
    safety: SafetyResult | None = None


class RegenerateResponse(BaseModel):
    job_id: str


# ---------------------------------------------------------------- 5. 돌아보기 (FR-005)

class SessionInfo(BaseModel):
    session_id: int
    started_at: datetime
    ended_at: datetime
    initiator: Who
    initiated_by_me: bool
    msg_count: int


class ReviewSessionMessage(BaseModel):
    message_id: int
    at: datetime
    mine: bool
    text: str


class ReviewSessionMessagesResponse(BaseModel):
    session_id: int
    total: int
    messages: list[ReviewSessionMessage]
    next_offset: int | None = None


class ReviewRange(BaseModel):
    start: datetime
    end: datetime


class RangeMetrics(BaseModel):
    """돌아보기 카드에 보여줄 지표 3개로 한정 (2026-08-25 결정, 윤아+윤석 병합).
    `message_count` 만 구간 합산 스칼라(개인별 미제공) — 나머지 2개는 CoupleMine.
    `message_length_median`·`session_length_median` 은 이 화면에서 뺌(타임라인/리포트에는 계속 있음)."""
    question_rate: CoupleMine
    reply_gap_median_min: CoupleMine   # 분 단위 — 타임라인·리포트와 단위 통일
    message_count: int

    @field_validator("question_rate")
    @classmethod
    def question_rate_is_ratio(cls, value: CoupleMine) -> CoupleMine:
        for item in (value.couple, value.mine):
            if item is not None and not 0 <= item <= 1:
                raise ValueError("question_rate는 0과 1 사이의 비율이어야 합니다")
        return value


class BaselineMetrics(BaseModel):
    """RangeMetrics와 기간 의미가 달라 별도 계약으로 유지한다(윤석, 2026-08-25).
    `message_count`는 날짜범위 모드에서 baseline 일평균을 선택 구간 길이로 환산한 값이라
    float일 수 있다 — RangeMetrics.message_count(정수 합산)와 타입이 다르다."""
    weeks: int = Field(ge=0, le=8)  # 기준선으로 쓴 과거 주 수 (보통 8)
    question_rate: CoupleMine
    reply_gap_median_min: CoupleMine
    message_count: float | None

    @field_validator("question_rate")
    @classmethod
    def question_rate_is_ratio(cls, value: CoupleMine) -> CoupleMine:
        for item in (value.couple, value.mine):
            if item is not None and not 0 <= item <= 1:
                raise ValueError("question_rate는 0과 1 사이의 비율이어야 합니다")
        return value


class ReviewMetrics(BaseModel):
    """`comment`: 방향성 문장 1줄. 숫자를 넣지 않는다 — 리포트 하이라이트와 같은 규칙(ISSUE B4).
    숫자는 위 range/baseline 카드가 이미 보여주므로, comment는 방향만 요약한다.
    실제 생성은 `services/review_metrics.py`의 `review_comment()`가 담당한다(LLM 미사용).
    예: "평소보다 답장 간격이 조금 길어졌어요." (O) / "3분 길어졌어요." (X)."""
    range: RangeMetrics
    baseline: BaselineMetrics
    comment: str


class NoteResponse(BaseModel):
    note_id: int
    author: Who
    body: str
    range_start: datetime | None = None
    range_end: datetime | None = None
    created_at: datetime


class ReviewResponse(BaseModel):
    range: ReviewRange
    sessions: list[SessionInfo]
    metrics: ReviewMetrics
    notes: list[NoteResponse]


class NoteCreateRequest(BaseModel):
    range_start: datetime
    range_end: datetime
    body: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------- 6. 챗봇 (FR-006)

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class FocusRange(BaseModel):
    start: datetime
    end: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    focus_range: FocusRange | None = None
    history: list[ChatTurn] = Field(default=[], max_length=6)


class Citation(BaseModel):
    session_id: int
    at: datetime
    sender: Who
    snippet: str


class ChatResponse(BaseModel):
    """`metrics`: metric_query 전용 카드 (2026-08-25 결정, ISSUE A7).
    숫자는 여기(range/baseline 카드)로만 나가고, `answer`는 comment 스타일로 방향만 말한다
    (metrics.comment를 그대로 쓰거나 질문에 맞게 살짝만 다듬는다 — 새 숫자 계산 금지, B4).
    metric_query가 아니면 항상 null."""
    intent: Intent
    answer: str | None
    citations: list[Citation] = []
    redirect: str | None = None
    trace_id: str
    metrics: ReviewMetrics | None = None


# ---------------------------------------------------------------- 7. 시스템

class HealthLiveResponse(BaseModel):
    status: str = "ok"


class HealthReadyResponse(BaseModel):
    postgres: bool
    qdrant: bool
    watsonx: bool | str  # true | "mock"
