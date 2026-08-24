"""외부 API 요청/응답 계약. API_SPEC.md의 Mock 단계 모델."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupRequest(APIModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=20)


class LoginRequest(APIModel):
    email: str
    password: str


class AuthResponse(APIModel):
    user_id: str
    token: str


class JoinRequest(APIModel):
    invite_code: str = Field(min_length=8, max_length=8)


class ConfirmRequest(APIModel):
    accept: bool


class CoupleStatusResponse(APIModel):
    couple_id: str
    status: Literal["pending", "awaiting_confirm", "active", "dissolved"]


class InviteResponse(CoupleStatusResponse):
    invite_code: str
    expires_at: datetime


class Partner(APIModel):
    display_name: str


class JoinResponse(CoupleStatusResponse):
    partner: Partner


class Member(APIModel):
    user_id: str
    display_name: str


class CoupleMeResponse(APIModel):
    couple_id: str | None = None
    status: str | None = None
    members: dict[str, Member] | None = None
    me: Literal["a", "b"] | None = None
    kakao_names: dict[str, str] | None = None
    started_at: date | None = None
    data: dict[str, Any] | None = None
    active_job: dict[str, Any] | None = None


class UploadResponse(APIModel):
    job_id: str
    embed_job: dict[str, str]
    parsed: dict[str, Any]
    weeks_computed: int
    report_jobs: dict[str, int]


class JobResponse(APIModel):
    job_id: str
    kind: Literal["embed_sessions", "build_lexicon", "report_backfill", "report_single"]
    status: Literal["running", "done", "failed"]
    progress: dict[str, int]
    current_week: date | None = None


class TimelineResponse(APIModel):
    weeks: list[dict[str, Any]]


class ReportResponse(APIModel):
    week_start: date
    status: Literal["generated", "insufficient_baseline", "pending", "failed"]
    summary: dict[str, Any]
    metrics: dict[str, Any] = Field(default_factory=dict)
    highlights: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    moments: list[dict[str, Any]] = Field(default_factory=list)
    safety: dict[str, Any] | None = None


class JobAcceptedResponse(APIModel):
    job_id: str


class ReviewResponse(APIModel):
    range: dict[str, datetime]
    sessions: list[dict[str, Any]]
    metrics: dict[str, Any]
    notes: list[dict[str, Any]]


class NoteCreateRequest(APIModel):
    range_start: datetime
    range_end: datetime
    body: str = Field(min_length=1, max_length=500)


class NoteResponse(NoteCreateRequest):
    note_id: int
    author: Literal["a", "b"]
    created_at: datetime


class FocusRange(APIModel):
    start: datetime
    end: datetime


class HistoryItem(APIModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(APIModel):
    message: str = Field(min_length=1, max_length=500)
    focus_range: FocusRange | None = None
    history: list[HistoryItem] = Field(default_factory=list, max_length=6)


class Citation(APIModel):
    session_id: int
    at: datetime
    sender: Literal["a", "b"]
    snippet: str


class ChatResponse(APIModel):
    intent: Literal[
        "fact_query",
        "metric_query",
        "report_query",
        "term_count",
        "advice_request",
        "other",
    ]
    answer: str | None
    citations: list[Citation]
    redirect: str | None
    trace_id: str


class LiveResponse(APIModel):
    status: Literal["ok"]


class ReadyResponse(APIModel):
    postgres: bool
    qdrant: bool
    watsonx: bool | Literal["mock"]

