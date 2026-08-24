// 역할: fetch 래퍼 — 토큰 주입, 에러 → {code, message} 파싱, USE_MOCK 분기 (참조: TRD §2.2, §6.4)
// 컴포넌트에서 직접 fetch 금지 — 반드시 이 모듈 경유 (SCAFFOLD §2)
import type { ApiError } from "./types";

const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === "true" || import.meta.env.USE_MOCK === "true";
const BASE = import.meta.env.VITE_API_BASE ?? ""; // 로컬은 vite proxy, 배포는 같은 Route 상대 경로

const TOKEN_KEY = "couple_report_token";

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

// VITE_USE_MOCK=true 또는 USE_MOCK=true면 API_SPEC 예시 JSON을 반환한다.
type MockLoader = () => Promise<{ default: unknown } | undefined>;

const MOCK_ROUTES: [RegExp, string, MockLoader][] = [
  [/^\/api\/auth\/(?:signup|login)$/, "POST", () => import("./mock/auth.json")],
  [/^\/api\/couples\/invite$/, "POST", () => import("./mock/invite.json")],
  [/^\/api\/couples\/join$/, "POST", () => import("./mock/join.json")],
  [/^\/api\/couples\/[^/]+\/confirm$/, "POST", () => import("./mock/confirm.json")],
  [/^\/api\/couples\/me$/, "GET", () => import("./mock/couples_me.json")],
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
    return (response?.default ?? undefined) as T;
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
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const err = (data ?? {}) as Partial<ApiError>;
    throw new ApiClientError(
      resp.status,
      err.error?.code ?? "ERROR",
      err.error?.message ?? resp.statusText,
      err.error?.detail,
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  postForm: <T>(path: string, form: FormData) => request<T>("POST", path, undefined, { form }),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
