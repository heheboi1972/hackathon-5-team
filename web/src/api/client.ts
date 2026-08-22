// 역할: fetch 래퍼 — 토큰 주입, 에러 → {code, message} 파싱, VITE_USE_MOCK 분기 (참조: TRD §2.2, §6.4)
// 컴포넌트에서 직접 fetch 금지 — 반드시 이 모듈 경유 (SCAFFOLD §2)
import type { ApiError } from "./types";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
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

// VITE_USE_MOCK=true 면 경로 → mock JSON 매핑 (백엔드 없이 화면 개발, TRD §6.4)
const MOCK_ROUTES: [RegExp, string, () => Promise<{ default: unknown }>][] = [
  [/^\/api\/auth\//, "POST", () => import("./mock/auth.json")],
  [/^\/api\/couples\/me$/, "GET", () => import("./mock/couples_me.json")],
  [/\/timeline/, "GET", () => import("./mock/timeline.json")],
  [/\/reports\//, "GET", () => import("./mock/report_generated.json")],
  [/\/chat$/, "POST", () => import("./mock/chat_fact.json")],
  [/^\/api\/jobs\//, "GET", () => import("./mock/job.json")],
  [/\/upload$/, "POST", () => import("./mock/upload.json")],
];

async function mockResponse<T>(path: string, method: string): Promise<T> {
  for (const [re, m, load] of MOCK_ROUTES) {
    if (m === method && re.test(path)) return (await load()).default as T;
  }
  throw new ApiClientError(404, "NOT_FOUND", `mock 없음: ${method} ${path}`);
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { form?: FormData } = {},
): Promise<T> {
  if (USE_MOCK) return mockResponse<T>(path, method);

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined && !opts.form) headers["Content-Type"] = "application/json";

  const resp = await fetch(`${BASE}${path}`, {
    method,
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
