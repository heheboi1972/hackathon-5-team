// 역할: fetch 래퍼 — 토큰 주입, 에러 → {code, message} 파싱, USE_MOCK 분기 (참조: TRD §2.2, §6.4)
// 컴포넌트에서 직접 fetch 금지 — 반드시 이 모듈 경유 (SCAFFOLD §2)
import type { ApiError, NoteCreateRequest, NoteResponse, ReviewResponse } from "./types";

// Only the Vite-prefixed flag may enable frontend fixtures. This keeps a
// production build from accidentally inheriting a generic USE_MOCK variable.
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const BASE = import.meta.env.VITE_API_BASE ?? ""; // 로컬은 vite proxy, 배포는 같은 Route 상대 경로

const TOKEN_KEY = "couple_report_token";
let mockCoupleFirstMetAt: string | null = null;
let mockCoupleFirstMetAtSet = false;

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token === null) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: Record<string, unknown>,
  ) {
    super(message);
  }
}

// VITE_USE_MOCK=true일 때만 API_SPEC 예시 JSON을 반환한다.
type MockLoader = () => Promise<{ default: unknown } | undefined>;

const MOCK_ROUTES: [RegExp, string, MockLoader][] = [
  [/^\/api\/auth\/(?:signup|login)$/, "POST", () => import("./mock/auth.json")],
  [/^\/api\/couples\/invite$/, "POST", () => import("./mock/invite.json")],
  [/^\/api\/couples\/join$/, "POST", () => import("./mock/join.json")],
  [/^\/api\/couples\/[^/]+\/confirm$/, "POST", () => import("./mock/confirm.json")],
  [/^\/api\/couples\/me$/, "GET", () => import("./mock/couples_me.json")],
  [/^\/api\/couples\/me$/, "PATCH", () => import("./mock/couples_me.json")],
  [/^\/api\/couples\/[^/]+\/upload$/, "POST", () => import("./mock/upload.json")],
  [/^\/api\/jobs\/[^/]+$/, "GET", () => import("./mock/job.json")],
  [/^\/api\/couples\/[^/]+\/timeline$/, "GET", () => import("./mock/timeline.json")],
  [
    /^\/api\/couples\/[^/]+\/reports\/[^/]+\/regenerate$/,
    "POST",
    () => import("./mock/regenerate.json"),
  ],
  [/^\/api\/couples\/[^/]+\/reports\/[^/]+$/, "GET", () => import("./mock/report_generated.json")],
  [/^\/api\/couples\/[^/]+\/review$/, "GET", () => import("./mock/review.json")],
  [/^\/api\/couples\/[^/]+\/notes$/, "POST", () => import("./mock/note.json")],
  [/^\/api\/couples\/[^/]+\/notes\/[^/]+$/, "DELETE", async () => undefined],
  [/^\/api\/couples\/[^/]+$/, "DELETE", async () => undefined],
  [/^\/health\/live$/, "GET", () => import("./mock/health_live.json")],
  [/^\/health\/ready$/, "GET", () => import("./mock/health_ready.json")],
];

function rangesOverlap(
  itemStart: string,
  itemEnd: string,
  selectedStart: string,
  selectedEnd: string,
): boolean {
  const itemStartTime = Date.parse(itemStart);
  const itemEndTime = Date.parse(itemEnd);
  const selectedStartTime = Date.parse(selectedStart);
  const selectedEndTime = Date.parse(selectedEnd);

  if (![itemStartTime, itemEndTime, selectedStartTime, selectedEndTime].every(Number.isFinite)) {
    return true;
  }
  return itemStartTime <= selectedEndTime && itemEndTime >= selectedStartTime;
}

function alignReviewMockToRequest(path: string, review: ReviewResponse): ReviewResponse {
  const params = new URL(path, "http://mock.local").searchParams;
  const start = params.get("start");
  const end = params.get("end");
  if (!start || !end) return review;

  return {
    ...review,
    range: { start, end },
    sessions: review.sessions.filter((session) =>
      rangesOverlap(session.started_at, session.ended_at, start, end),
    ),
    notes: review.notes.filter((note) => {
      const noteStart = note.range_start ?? note.created_at;
      const noteEnd = note.range_end ?? noteStart;
      return rangesOverlap(noteStart, noteEnd, start, end);
    }),
  };
}

function alignNoteMockToRequest(body: unknown, note: NoteResponse): NoteResponse {
  if (typeof body !== "object" || body === null) return note;
  const payload = body as Partial<NoteCreateRequest>;
  return {
    ...note,
    body: typeof payload.body === "string" ? payload.body : note.body,
    range_start:
      typeof payload.range_start === "string" ? payload.range_start : note.range_start,
    range_end: typeof payload.range_end === "string" ? payload.range_end : note.range_end,
  };
}

async function mockResponse<T>(path: string, method: string, body?: unknown): Promise<T> {
  const pathname = path.split("?", 1)[0];

  // API_SPEC의 챗봇 예시 3종을 요청 문장에 따라 선택한다.
  if (method === "POST" && /\/chat$/.test(pathname)) {
    const message =
      typeof body === "object" && body !== null && "message" in body &&
      typeof body.message === "string"
        ? body.message
        : "";

    if (/몇\s*(번|회)|얼마나\s*자주/.test(message)) {
      return (await import("./mock/chat_count.json")).default as T;
    }
    if (/조언|관계.*어떻|어떻게.*(해야|할까)/.test(message)) {
      return (await import("./mock/chat_advice.json")).default as T;
    }
    return (await import("./mock/chat_fact.json")).default as T;
  }

  for (const [re, routeMethod, load] of MOCK_ROUTES) {
    if (routeMethod !== method || !re.test(pathname)) continue;
    const response = await load();
    const fixture = response?.default ?? undefined;
    if (pathname === "/api/couples/me" && method === "PATCH") {
      const payload = body as { first_met_at?: unknown } | undefined;
      if (!payload || !("first_met_at" in payload) ||
          (payload.first_met_at !== null && typeof payload.first_met_at !== "string")) {
        throw new ApiClientError(422, "VALIDATION_ERROR", "first_met_at 형식이 올바르지 않습니다.");
      }
      mockCoupleFirstMetAt = payload.first_met_at;
      mockCoupleFirstMetAtSet = true;
    }
    if (pathname === "/api/couples/me" && method === "GET" && mockCoupleFirstMetAtSet) {
      return {
        ...(fixture as Record<string, unknown>),
        first_met_at: mockCoupleFirstMetAt,
      } as T;
    }
    if (pathname === "/api/couples/me" && method === "PATCH") {
      return {
        ...(fixture as Record<string, unknown>),
        first_met_at: mockCoupleFirstMetAt,
      } as T;
    }
    if (method === "GET" && /\/review$/.test(pathname)) {
      return alignReviewMockToRequest(path, fixture as ReviewResponse) as T;
    }
    if (method === "POST" && /\/notes$/.test(pathname)) {
      return alignNoteMockToRequest(body, fixture as NoteResponse) as T;
    }
    return fixture as T;
  }
  throw new ApiClientError(404, "NOT_FOUND", `mock 없음: ${method} ${path}`);
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { form?: FormData } = {},
): Promise<T> {
  const normalizedMethod = method.toUpperCase();
  if (USE_MOCK) return mockResponse<T>(path, normalizedMethod, body);

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined && !opts.form) headers["Content-Type"] = "application/json";

  const resp = await fetch(`${BASE}${path}`, {
    method: normalizedMethod,
    headers,
    body: opts.form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (resp.status === 204) return undefined as T;

  const text = await resp.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      if (!resp.ok) {
        throw new ApiClientError(
          resp.status,
          "NON_JSON_ERROR",
          resp.status >= 500
            ? "서버에서 오류가 발생했어요. 잠시 후 다시 시도해주세요."
            : "요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
        );
      }
      throw new ApiClientError(
        resp.status,
        "INVALID_RESPONSE",
        "서버 응답을 읽지 못했어요. 잠시 후 다시 시도해주세요.",
      );
    }
  }
  if (!resp.ok) {
    const err = (data ?? {}) as Partial<ApiError> & { detail?: unknown };
    const fastApiDetail =
      typeof err.detail === "object" && err.detail !== null && !Array.isArray(err.detail)
        ? err.detail as { code?: string; message?: string; detail?: Record<string, unknown> }
        : undefined;
    const apiError = err.error ?? fastApiDetail;
    throw new ApiClientError(
      resp.status,
      apiError?.code ?? "ERROR",
      apiError?.message ?? resp.statusText,
      apiError?.detail,
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  postForm: <T>(path: string, form: FormData) => request<T>("POST", path, undefined, { form }),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
