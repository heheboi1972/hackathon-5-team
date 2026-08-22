# 역할: API 요청/응답 Pydantic 모델 — web/src/api/types.ts 와 1:1 계약 (참조: docs/API_SPEC.md)
# 변경 시 팀 채널 공지 + types.ts 동기화 (SCAFFOLD §3 충돌 방지 규칙)
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

Who = Literal["a", "b"]
CoupleStatus = Literal["pending", "awaiting_confirm", "active", "dissolved"]
ReportStatus = Literal["generated", "insufficient_baseline", "pending", "failed"]
JobStatus = Literal["queued", "running", "done", "failed"]
Intent = Literal["fact_query", "metric_query", "report_query", "advice_request", "other"]
Sentiment = Literal["positive", "neutral", "notable"]


# ---------------------------------------------------------------- 공통

class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ABFloat(BaseModel):
    a: float
    b: float


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


class CoupleMeResponse(BaseModel):
    couple_id: str | None = None
    status: CoupleStatus | None = None
    members: CoupleMembers | None = None
    me: Who | None = None
    kakao_names: dict[Who, str] | None = None
    started_at: date | None = None
    data: CoupleData | None = None


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


class UploadResponse(BaseModel):
    job_id: str
    parsed: ParsedInfo
    weeks_computed: int
    report_jobs: ReportJobsInfo


class JobProgress(BaseModel):
    total: int
    done: int
    failed: int


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: JobProgress
    current_week: date | None = None


# ---------------------------------------------------------------- 4. 타임라인·리포트 (FR-003, FR-004)

class WeekSummary(BaseModel):
    session_count: int
    message_count: int
    initiation_ratio: ABFloat
    question_rate: ABFloat
    message_length_median: ABFloat
    reply_gap_median_min: ABFloat
    resume_delay_median_min: ABFloat
    session_length_median: float


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
    a: float | None = None
    b: float | None = None
    baseline_a: float | None = None
    baseline_b: float | None = None
    delta_a: float | None = None
    delta_b: float | None = None
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
    who: Who
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
    who: Who
    at: datetime
    session_id: int
    value_min: float | None = None
    baseline_median_min: float | None = None
    text: str


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
    msg_count: int


class ReviewRange(BaseModel):
    start: datetime
    end: datetime


class ReviewMetrics(BaseModel):
    range: dict[str, Any]
    baseline: dict[str, Any]


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
    intent: Intent
    answer: str | None
    citations: list[Citation] = []
    redirect: str | None = None
    trace_id: str


# ---------------------------------------------------------------- 7. 시스템

class HealthLiveResponse(BaseModel):
    status: str = "ok"


class HealthReadyResponse(BaseModel):
    postgres: bool
    qdrant: bool
    watsonx: bool | str  # true | "mock"
