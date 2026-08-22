// 역할: API_SPEC 응답 타입 — api/app/models/api.py 와 1:1 계약 (참조: docs/API_SPEC.md)
// 변경 시 팀 채널 공지 + models/api.py 동기화 (SCAFFOLD §3 충돌 방지 규칙)

export type Who = "a" | "b";
export type CoupleStatus = "pending" | "awaiting_confirm" | "active" | "dissolved";
export type ReportStatus = "generated" | "insufficient_baseline" | "pending" | "failed";
export type JobStatus = "queued" | "running" | "done" | "failed";
export type Intent = "fact_query" | "metric_query" | "report_query" | "advice_request" | "other";
export type Sentiment = "positive" | "neutral" | "notable";

// ---------------------------------------------------------------- 공통

export interface ApiError {
  error: { code: string; message: string; detail?: Record<string, unknown> };
}

export interface ABFloat {
  a: number;
  b: number;
}

// ---------------------------------------------------------------- 1. 인증 (FR-000)

export interface SignupRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  user_id: string;
  token: string;
}

// ---------------------------------------------------------------- 2. 커플 연결 (FR-001)

export interface InviteResponse {
  couple_id: string;
  invite_code: string;
  expires_at: string;
  status: CoupleStatus;
}

export interface JoinRequest {
  invite_code: string;
}

export interface JoinResponse {
  couple_id: string;
  status: CoupleStatus;
  partner: { display_name: string };
}

export interface ConfirmRequest {
  accept: boolean;
}

export interface ConfirmResponse {
  couple_id: string;
  status: CoupleStatus;
}

export interface MemberInfo {
  user_id: string;
  display_name: string;
}

export interface CoupleMeResponse {
  couple_id: string | null;
  status: CoupleStatus | null;
  members?: { a: MemberInfo; b: MemberInfo } | null;
  me?: Who | null;
  kakao_names?: Record<Who, string> | null;
  started_at?: string | null;
  data?: {
    first_week: string;
    last_week: string;
    weeks_available: number;
    message_count: number;
  } | null;
}

// ---------------------------------------------------------------- 3. 업로드 (FR-002)

export interface UploadResponse {
  job_id: string;
  parsed: {
    format: "pc" | "ios" | "android";
    message_count: number;
    new_messages: number;
    session_count: number;
    range: { from: string; to: string };
  };
  weeks_computed: number;
  report_jobs: { total: number; pending: number };
}

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  progress: { total: number; done: number; failed: number };
  current_week?: string | null;
}

// ---------------------------------------------------------------- 4. 타임라인·리포트 (FR-003, FR-004)

export interface WeekSummary {
  session_count: number;
  message_count: number;
  initiation_ratio: ABFloat;
  question_rate: ABFloat;
  message_length_median: ABFloat;
  reply_gap_median_min: ABFloat;
  resume_delay_median_min: ABFloat;
  session_length_median: number;
}

export interface TimelineWeek {
  week_start: string;
  in_progress: boolean;
  report_status: ReportStatus;
  summary: WeekSummary;
  outlier_count: number;
  events: Record<string, unknown>[];
}

export interface TimelineResponse {
  weeks: TimelineWeek[];
}

export interface MetricComparison {
  a?: number | null;
  b?: number | null;
  baseline_a?: number | null;
  baseline_b?: number | null;
  delta_a?: number | null;
  delta_b?: number | null;
  comparable: boolean;
}

export interface Evidence {
  session_id: number;
  at: string;
  snippet: string;
}

export interface Source {
  doc: string;
  section: string;
}

export interface Highlight {
  id: string;
  metric: string;
  who: Who;
  observation: string;
  interpretations: string[]; // 불변 규칙: 길이 >= 2
  evidence: Evidence[];
  sources: Source[];
  sentiment: Sentiment;
}

export interface Suggestion {
  id: string;
  linked_highlight: string;
  template_id: string;
  text: string;
}

export interface Moment {
  kind: string;
  who: Who;
  at: string;
  session_id: number;
  value_min?: number | null;
  baseline_median_min?: number | null;
  text: string;
}

export interface ReportResponse {
  week_start: string;
  status: ReportStatus;
  summary?: WeekSummary | null;
  metrics: Record<string, MetricComparison>;
  highlights: Highlight[];
  suggestions: Suggestion[];
  moments: Moment[];
  safety?: { passed: boolean; rewritten: { before: string; after: string }[] } | null;
}

export interface RegenerateResponse {
  job_id: string;
}

// ---------------------------------------------------------------- 5. 돌아보기 (FR-005)

export interface SessionInfo {
  session_id: number;
  started_at: string;
  ended_at: string;
  initiator: Who;
  msg_count: number;
}

export interface NoteResponse {
  note_id: number;
  author: Who;
  body: string;
  range_start?: string | null;
  range_end?: string | null;
  created_at: string;
}

export interface ReviewResponse {
  range: { start: string; end: string };
  sessions: SessionInfo[];
  metrics: {
    range: Record<string, unknown>;
    baseline: Record<string, unknown>;
  };
  notes: NoteResponse[];
}

export interface NoteCreateRequest {
  range_start: string;
  range_end: string;
  body: string;
}

// ---------------------------------------------------------------- 6. 챗봇 (FR-006)

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  focus_range?: { start: string; end: string };
  history?: ChatTurn[];
}

export interface Citation {
  session_id: number;
  at: string;
  sender: Who;
  snippet: string;
}

export interface ChatResponse {
  intent: Intent;
  answer: string | null;
  citations: Citation[];
  redirect: string | null;
  trace_id: string;
}

// ---------------------------------------------------------------- 7. 시스템

export interface HealthReadyResponse {
  postgres: boolean;
  qdrant: boolean;
  watsonx: boolean | "mock";
}
