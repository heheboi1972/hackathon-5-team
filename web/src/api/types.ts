// 역할: API_SPEC 응답 타입 — api/app/models/api.py 와 1:1 계약 (참조: docs/API_SPEC.md)
// 변경 시 팀 채널 공지 + models/api.py 동기화 (SCAFFOLD §3 충돌 방지 규칙)

export type Who = "a" | "b";
export type CoupleStatus = "pending" | "awaiting_confirm" | "active" | "dissolved";
export type ReportStatus = "generated" | "insufficient_baseline" | "pending" | "failed";
export type JobStatus = "queued" | "running" | "done" | "failed";
export type JobKind = "embed_sessions" | "build_lexicon" | "report_backfill" | "report_single";
export type Intent = "fact_query" | "metric_query" | "report_query" | "term_count" | "advice_request" | "other";
export type Sentiment = "positive" | "neutral" | "notable";

// ---------------------------------------------------------------- 공통

export interface ApiError {
  error: { code: string; message: string; detail?: Record<string, unknown> };
}

/** 커플 합산 + 요청자 본인 값. 상대 값은 응답에 담기지 않는다 (P-3 예외, ISSUE B3) */
export interface CoupleMine {
  couple: number | null;
  mine: number | null;
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
  first_met_at?: string | null;
  data?: {
    first_week: string;
    last_week: string;
    weeks_available: number;
    message_count: number;
  } | null;
  /** 진행 중인 잡 (새로고침 후 진행률 복구용). 없으면 null */
  active_job?: { job_id: string; kind: JobKind; done: number; total: number } | null;
}

export interface CoupleSettingsUpdate {
  first_met_at: string | null;
}

// ---------------------------------------------------------------- 3. 업로드 (FR-002)

export interface UploadResponse {
  job_id: string;                    // 리포트 잡 (report_backfill)
  embed_job: { job_id: string };     // 임베딩 잡 (embed_sessions) — 리포트 잡보다 먼저 실행
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
  kind: JobKind;
  status: JobStatus;
  progress: { total: number; done: number; failed: number };
  current_week?: string | null;
}

// ---------------------------------------------------------------- 4. 타임라인·리포트 (FR-003, FR-004)

/** 활발한 요일·시간대 (커플 합산). 메시지 없으면 top_* null */
export interface Activity {
  top_weekday: number | null;   // 0=월 … 6=일
  top_hour: number | null;      // 0~23
  by_weekday: number[];         // 길이 7
  by_hour: number[];            // 길이 24
}

export interface TermCount {
  canonical: string;
  count: number;
}

/** "내 단어" — 요청자 본인의 pos/neg 상위 3 (count<3 숨김). 상대 데이터는 오지 않음 (P-3 예외) */
export interface MyTerms {
  pos: TermCount[];
  neg: TermCount[];
}

export interface WeekSummary {
  session_count: number;
  message_count: number;
  question_rate: CoupleMine;
  message_length_median: CoupleMine;
  reply_gap_median_min: CoupleMine;
  resume_delay_median_min: CoupleMine;
  session_length_median: number;
  activity: Activity;
  sentiment?: MyTerms | null;   // 사전 미구축 시 null
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

/** 리포트 문장·하이라이트는 couple 기준 (ISSUE B3) */
export interface MetricComparison {
  couple?: number | null;
  mine?: number | null;
  baseline_couple?: number | null;
  baseline_mine?: number | null;
  delta_couple?: number | null;
  delta_mine?: number | null;
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
  at: string;
  session_id: number;
  value_min?: number | null;
  baseline_median_min?: number | null;
  text: string;
  snippet?: string | null;
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

// 돌아보기 카드 지표 3개로 한정 (2026-08-25 결정, ISSUE D4 해소).
// message_length_median·session_length_median 은 이 화면에서 뺌 (타임라인/리포트에는 그대로 있음).
export interface RangeMetrics {
  question_rate: CoupleMine;
  reply_gap_median_min: CoupleMine; // 분 단위 — 타임라인·리포트와 단위 통일
  message_count: number; // 구간 합산, 개인별 미제공
}

// RangeMetrics와 기간 의미가 달라 별도 타입으로 유지 (윤석, 2026-08-25).
// message_count는 날짜범위 모드에서 baseline 일평균을 선택 구간 길이로 환산한 값이라 null일 수 있음.
export interface BaselineMetrics {
  weeks: number; // 기준선으로 쓴 과거 주 수 (보통 8, 최대 8)
  question_rate: CoupleMine;
  reply_gap_median_min: CoupleMine;
  message_count: number | null;
}

export interface ReviewMetrics {
  range: RangeMetrics;
  baseline: BaselineMetrics;
  // 방향성 문장 1줄. 숫자 없음 — 리포트 하이라이트와 같은 규칙(ISSUE B4). 숫자는 위 카드가 이미 보여줌.
  comment: string;
}

export interface ReviewResponse {
  range: { start: string; end: string };
  sessions: SessionInfo[];
  metrics: ReviewMetrics;
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
  // metric_query 전용 카드 (2026-08-25 결정, ISSUE A7). 숫자는 여기로만 나가고 answer는 방향 문장만.
  // metric_query가 아니면 항상 null.
  metrics: ReviewMetrics | null;
}

// ---------------------------------------------------------------- 7. 시스템

export interface HealthReadyResponse {
  postgres: boolean;
  qdrant: boolean;
  watsonx: boolean | "mock";
}
