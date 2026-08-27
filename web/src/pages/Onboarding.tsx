// 역할: 온보딩 — 가입 → 초대코드 → 즉시 연결 (참조: FR-000, FR-001, TRD §6.1) — 시여 담당
import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, getToken, setToken } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import type {
  AuthResponse,
  ConfirmResponse,
  CoupleMeResponse,
  InviteResponse,
  JoinResponse,
  LoginRequest,
  SignupRequest,
} from "../api/types";

type OnboardingStage = "signup" | "invite" | "awaiting" | "active";
type AuthMode = "signup" | "login";
type InviteMode = "create" | "join" | null;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청을 처리하지 못했어요.";
}

export default function Onboarding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<OnboardingStage>("signup");
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [isRestoringSession, setIsRestoringSession] = useState(() => Boolean(getToken()));
  const [form, setForm] = useState<SignupRequest>({
    email: "",
    password: "",
    display_name: "",
  });
  const [loginForm, setLoginForm] = useState<LoginRequest>({ email: "", password: "" });
  const [invite, setInvite] = useState<InviteResponse | null>(null);
  const [inviteMode, setInviteMode] = useState<InviteMode>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isRestoringSession) return;

    let cancelled = false;
    const restoreSession = async () => {
      try {
        const me = await api.get<CoupleMeResponse>("/api/couples/me");
        if (cancelled) return;
        if (me.status === "active") navigate("/", { replace: true });
        else if (me.couple_id && me.status === "awaiting_confirm") setStage("awaiting");
        else setStage("invite");
      } catch {
        if (!cancelled) {
          setToken(null);
          queryClient.removeQueries({ queryKey: ["couple-me"] });
        }
      } finally {
        if (!cancelled) setIsRestoringSession(false);
      }
    };

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [isRestoringSession, navigate, queryClient]);

  useEffect(() => {
    if (!getToken() || (stage !== "invite" && stage !== "awaiting")) return;

    let cancelled = false;
    const syncConnection = async () => {
      try {
        const me = await api.get<CoupleMeResponse>("/api/couples/me");
        if (cancelled || !me.couple_id || !me.status) return;
        if (me.status === "active") setStage("active");
        else if (me.status === "awaiting_confirm") {
          // 이전 배포본의 수락 대기도 어느 한쪽 화면에서 자동으로 완료한다.
          const confirmed = await api.post<ConfirmResponse>(
            `/api/couples/${me.couple_id}/confirm`,
            { accept: true },
          );
          if (!cancelled && confirmed.status === "active") setStage("active");
        }
      } catch {
        // 연결 완료 확인은 보조 요청이므로, 일시적 오류는 다음 주기에 다시 시도한다.
      }
    };

    void syncConnection();
    const timer = window.setInterval(() => void syncConnection(), 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [stage]);

  const updateForm = (field: keyof SignupRequest, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const updateLoginForm = (field: keyof LoginRequest, value: string) => {
    setLoginForm((current) => ({ ...current, [field]: value }));
  };

  const goToNextStageAfterAuth = async () => {
    const me = await api.get<CoupleMeResponse>("/api/couples/me");
    if (me.status === "active") {
      navigate("/", { replace: true });
      return;
    }
    if (me.couple_id && me.status === "awaiting_confirm") {
      setStage("awaiting");
      return;
    }
    setStage("invite");
  };

  const signup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = form.email.trim();
    const displayName = form.display_name.trim();

    if (!email.includes("@")) {
      setError("이메일 주소를 입력해주세요.");
      return;
    }
    if (form.password.length < 8) {
      setError("비밀번호는 8자 이상이어야 해요.");
      return;
    }
    if (displayName.length < 1 || displayName.length > 20) {
      setError("이름은 1~20자로 입력해주세요.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await api.post<AuthResponse>("/api/auth/signup", {
        email,
        password: form.password,
        display_name: displayName,
      });
      setToken(result.token);
      queryClient.removeQueries({ queryKey: ["couple-me"] });
      setStage("invite");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = loginForm.email.trim();

    if (!email.includes("@")) {
      setError("이메일 주소를 입력해주세요.");
      return;
    }
    if (loginForm.password.length < 1) {
      setError("비밀번호를 입력해주세요.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await api.post<AuthResponse>("/api/auth/login", {
        email,
        password: loginForm.password,
      });
      setToken(result.token);
      queryClient.removeQueries({ queryKey: ["couple-me"] });
      await goToNextStageAfterAuth();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const createInvite = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await api.post<InviteResponse>("/api/couples/invite");
      setInvite(result);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const join = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = inviteCode.trim().toUpperCase();
    if (code.length !== 8) {
      setError("초대 코드는 8자리로 입력해주세요.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await api.post<JoinResponse>("/api/couples/join", {
        invite_code: code,
      });
      setStage(result.status === "active" ? "active" : "awaiting");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="onboarding-page">
      <div className="onboarding-background-decor" aria-hidden="true">
        <span className="onboarding-decor-cloud onboarding-decor-cloud--one" />
        <span className="onboarding-decor-cloud onboarding-decor-cloud--two" />
        <span className="onboarding-decor-sparkle onboarding-decor-sparkle--one">✦</span>
        <span className="onboarding-decor-sparkle onboarding-decor-sparkle--two">✧</span>
        <span className="onboarding-flight-path" />
      </div>

      <div className="onboarding-shell">
      {false && stage === "signup" && (
        <Card>
          <div className="mb-5 flex items-center justify-between">
            <div className="space-y-1">
              <Badge tone="neutral">1단계</Badge>
              <h2 className="text-lg font-semibold">
                {authMode === "signup" ? "계정 만들기" : "로그인"}
              </h2>
              <p className="text-sm text-gray-600">
                {authMode === "signup"
                  ? "리포트를 확인할 계정 정보를 입력해주세요."
                  : "가입할 때 사용한 이메일과 비밀번호를 입력해주세요."}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setAuthMode(authMode === "signup" ? "login" : "signup");
                setError(null);
              }}
              className="shrink-0 text-sm font-medium text-rose-600 hover:underline"
            >
              {authMode === "signup" ? "이미 계정이 있어요" : "처음이에요"}
            </button>
          </div>

          {authMode === "signup" ? (
            <form className="space-y-4" onSubmit={signup}>
              <label className="block space-y-1 text-sm font-medium text-gray-700">
                이메일
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => updateForm("email", event.target.value)}
                  autoComplete="email"
                  placeholder="you@example.com"
                  className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  required
                />
              </label>
              <label className="block space-y-1 text-sm font-medium text-gray-700">
                비밀번호
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => updateForm("password", event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  placeholder="8자 이상"
                  className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  required
                />
              </label>
              <label className="block space-y-1 text-sm font-medium text-gray-700">
                표시 이름
                <input
                  type="text"
                  value={form.display_name}
                  onChange={(event) => updateForm("display_name", event.target.value)}
                  autoComplete="name"
                  maxLength={20}
                  placeholder="1~20자"
                  className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  required
                />
              </label>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "가입 중…" : "가입하고 계속하기"}
              </Button>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={login}>
              <label className="block space-y-1 text-sm font-medium text-gray-700">
                이메일
                <input
                  type="email"
                  value={loginForm.email}
                  onChange={(event) => updateLoginForm("email", event.target.value)}
                  autoComplete="email"
                  placeholder="you@example.com"
                  className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  required
                />
              </label>
              <label className="block space-y-1 text-sm font-medium text-gray-700">
                비밀번호
                <input
                  type="password"
                  value={loginForm.password}
                  onChange={(event) => updateLoginForm("password", event.target.value)}
                  autoComplete="current-password"
                  placeholder="비밀번호"
                  className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  required
                />
              </label>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "로그인 중…" : "로그인"}
              </Button>
            </form>
          )}
        </Card>
      )}

        {!isRestoringSession && <ol className="onboarding-progress" aria-label="온보딩 진행 단계">
          {[
            ["signup", "가입"],
            ["invite", "초대"],
            ["awaiting", "대기"],
            ["active", "완료"],
          ].map(([key, label], index) => {
            const stages: OnboardingStage[] = ["signup", "invite", "awaiting", "active"];
            const currentIndex = stages.indexOf(stage);
            const complete = index <= currentIndex;
            return (
              <li
                key={key}
                className={[
                  "onboarding-progress__step",
                  index === currentIndex ? "is-active" : "",
                  complete && index !== currentIndex ? "is-complete" : "",
                ].filter(Boolean).join(" ")}
                aria-current={index === currentIndex ? "step" : undefined}
              >
                <span className="onboarding-progress__number">{index + 1}</span>
                <span>{label}</span>
              </li>
            );
          })}
        </ol>}

        <div className="onboarding-flow">
          {isRestoringSession ? (
            <Card className="onboarding-card onboarding-state-card">
              <Badge tone="neutral" className="onboarding-badge">로그인 확인 중</Badge>
              <h2>이전 로그인을 불러오고 있어요</h2>
              <p>잠시만 기다려주세요.</p>
            </Card>
          ) : stage === "signup" ? (
            <Card className="onboarding-card onboarding-card--signup">
              <div className="onboarding-card__heading">
                <span className="onboarding-step-icon onboarding-step-icon--pink" aria-hidden="true">♡</span>
                <div>
                  <Badge tone="neutral" className="onboarding-badge">1단계 · 시작</Badge>
                  <h2>{authMode === "signup" ? "계정 만들기" : "로그인"}</h2>
                  <p>
                    {authMode === "signup"
                      ? "리포트를 확인할 계정 정보를 입력해주세요."
                      : "가입할 때 사용한 이메일과 비밀번호를 입력해주세요."}
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="onboarding-auth-switch"
                onClick={() => {
                  setAuthMode((current) => (current === "signup" ? "login" : "signup"));
                  setError(null);
                }}
              >
                {authMode === "signup" ? "이미 계정이 있어요" : "처음이에요"}
              </button>
              {authMode === "signup" ? (
              <form className="onboarding-form" onSubmit={signup}>
                <label className="onboarding-field">
                  <span>이메일</span>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) => updateForm("email", event.target.value)}
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="onboarding-input"
                    required
                  />
                </label>
                <label className="onboarding-field">
                  <span>비밀번호</span>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(event) => updateForm("password", event.target.value)}
                    autoComplete="new-password"
                    minLength={8}
                    placeholder="8자 이상"
                    className="onboarding-input"
                    required
                  />
                </label>
                <label className="onboarding-field">
                  <span>표시 이름</span>
                  <input
                    type="text"
                    value={form.display_name}
                    onChange={(event) => updateForm("display_name", event.target.value)}
                    autoComplete="name"
                    maxLength={20}
                    placeholder="1~20자"
                    className="onboarding-input"
                    required
                  />
                </label>
                <Button type="submit" className="onboarding-primary-button w-full" disabled={isSubmitting}>
                  {isSubmitting ? "가입 중…" : "가입하고 계속하기"}
                </Button>
              </form>
              ) : (
                <form className="onboarding-form" onSubmit={login}>
                  <label className="onboarding-field">
                    <span>이메일</span>
                    <input
                      type="email"
                      value={loginForm.email}
                      onChange={(event) => updateLoginForm("email", event.target.value)}
                      autoComplete="email"
                      placeholder="you@example.com"
                      className="onboarding-input"
                      required
                    />
                  </label>
                  <label className="onboarding-field">
                    <span>비밀번호</span>
                    <input
                      type="password"
                      value={loginForm.password}
                      onChange={(event) => updateLoginForm("password", event.target.value)}
                      autoComplete="current-password"
                      placeholder="비밀번호"
                      className="onboarding-input"
                      required
                    />
                  </label>
                  <Button type="submit" className="onboarding-primary-button w-full" disabled={isSubmitting}>
                    {isSubmitting ? "로그인 중…" : "로그인"}
                  </Button>
                </form>
              )}
            </Card>
          ) : null}

          {stage === "invite" && (
            <div className="onboarding-invite-stack">
              {inviteMode === null && (
                <Card className="onboarding-card onboarding-card--invite-choice">
                  <div className="onboarding-card__heading">
                    <span className="onboarding-step-icon onboarding-step-icon--lavender" aria-hidden="true">↗</span>
                    <div>
                      <Badge tone="neutral" className="onboarding-badge">2단계 · 우리 연결</Badge>
                      <h2>어떻게 연결할까요?</h2>
                      <p>한 사람은 코드를 만들고, 다른 사람은 받은 코드를 입력해주세요.</p>
                    </div>
                  </div>
                  <div className="onboarding-invite-options">
                    <button type="button" onClick={() => setInviteMode("create")}>
                      <span aria-hidden="true">↗</span>
                      <strong>초대 코드 만들기</strong>
                      <small>상대방에게 전달할 코드를 발급해요</small>
                    </button>
                    <button type="button" onClick={() => setInviteMode("join")}>
                      <span aria-hidden="true">♡</span>
                      <strong>초대 코드 입력하기</strong>
                      <small>상대방에게 받은 8자리 코드를 입력해요</small>
                    </button>
                  </div>
                </Card>
              )}

              {inviteMode === "create" && <Card className="onboarding-card onboarding-card--invite">
                <div className="onboarding-card__heading">
                  <span className="onboarding-step-icon onboarding-step-icon--lavender" aria-hidden="true">↗</span>
                  <div>
                    <Badge tone="neutral" className="onboarding-badge">2단계 · 우리 연결</Badge>
                    <h2>서로를 연결해볼까요?</h2>
                    <p>상대방에게 전달할 초대 코드를 발급해주세요.</p>
                  </div>
                </div>
                <Button onClick={createInvite} disabled={isSubmitting} className="onboarding-primary-button">
                  {isSubmitting ? "발급 중…" : invite ? "코드 다시 확인하기" : "초대 코드 발급"}
                </Button>
                {invite && (
                  <div className="onboarding-invite-code">
                    <span className="onboarding-invite-code__label">우리만의 연결 코드</span>
                    <strong>{invite.invite_code}</strong>
                    <span>코드는 7일 동안 유효해요.</span>
                  </div>
                )}
                <button type="button" className="onboarding-back-button" onClick={() => setInviteMode(null)}>
                  다른 방법 선택
                </button>
              </Card>}

              {inviteMode === "join" && <Card className="onboarding-card onboarding-card--join">
                <div className="onboarding-card__heading">
                  <span className="onboarding-step-icon onboarding-step-icon--peach" aria-hidden="true">♡</span>
                  <div>
                    <Badge tone="neutral" className="onboarding-badge">상대방</Badge>
                    <h2>받은 초대 코드 입력</h2>
                    <p>전달받은 8자리 코드를 입력해주세요.</p>
                  </div>
                </div>
                <form className="onboarding-join-form" onSubmit={join}>
                  <input
                    value={inviteCode}
                    onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                    placeholder="K7P2M9QX"
                    maxLength={8}
                    className="onboarding-input onboarding-code-input"
                    aria-label="초대 코드"
                    required
                  />
                  <Button type="submit" disabled={isSubmitting} className="onboarding-primary-button">
                    연결 요청
                  </Button>
                </form>
                <button type="button" className="onboarding-back-button" onClick={() => setInviteMode(null)}>
                  다른 방법 선택
                </button>
              </Card>}
            </div>
          )}

          {stage === "awaiting" && (
            <Card className="onboarding-card onboarding-state-card onboarding-card--awaiting">
              <div className="onboarding-state-visual onboarding-state-visual--waiting" aria-hidden="true">
                <span>♡</span><i>↗</i>
              </div>
              <Badge tone="neutral" className="onboarding-badge">3단계 · 연결 확인 중</Badge>
              <h2>연결을 마무리하고 있어요</h2>
              <p>잠시 후 두 사람 모두 자동으로 연결 완료 화면으로 이동해요.</p>
            </Card>
          )}

          {stage === "active" && (
            <Card className="onboarding-card onboarding-state-card onboarding-card--active">
              <div className="onboarding-state-visual onboarding-state-visual--active" aria-hidden="true">
                <span>♥</span><i>✓</i>
              </div>
              <Badge tone="neutral" className="onboarding-badge">4단계 · 연결 완료</Badge>
              <h2>우리의 공간이 연결됐어요</h2>
              <p>이제 대화 파일을 올리고 리포트를 준비할 수 있어요.</p>
              <Link to="/upload" className="onboarding-primary-link">
                대화 파일 업로드하기
              </Link>
            </Card>
          )}

          {error && (
            <p role="alert" className="onboarding-error">
              {error}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
