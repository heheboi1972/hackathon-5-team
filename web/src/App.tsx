// 역할: 라우트 정의 (참조: TRD §6.1) — 가드(couples/me 분기)는 TODO(시여)
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import Onboarding from "./pages/Onboarding";
import Report from "./pages/Report";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Timeline from "./pages/Timeline";
import Upload from "./pages/Upload";

const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === "true" || import.meta.env.USE_MOCK === "true";

const navigationItems = [
  { label: "타임라인", icon: "home", path: "/", matches: (pathname: string) => pathname === "/" || pathname.startsWith("/timeline") },
  { label: "주간 리포트", icon: "calendar", path: "/report", matches: (pathname: string) => pathname === "/report" || pathname.startsWith("/reports/") },
  { label: "돌아보기", icon: "chat", path: "/review", matches: (pathname: string) => pathname.startsWith("/review") },
  { label: "챗봇", icon: "chat", path: "/chat", matches: (pathname: string) => pathname.startsWith("/chat") },
  { label: "대화 올리기", icon: "upload", path: "/upload", matches: (pathname: string) => pathname.startsWith("/upload") },
  { label: "설정", icon: "settings", path: "/settings", matches: (pathname: string) => pathname.startsWith("/settings") },
];

function NavIcon({ name }: { name: string }) {
  if (name === "home") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3.5 10.5 8.5-7 8.5 7v9a1 1 0 0 1-1 1h-5v-5h-5v5h-5a1 1 0 0 1-1-1Z" /></svg>;
  if (name === "calendar") return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16M8 14h.01M12 14h.01M16 14h.01" /></svg>;
  if (name === "chat") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5.5h14a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5H11l-4.5 3v-3H5A2.5 2.5 0 0 1 2.5 15.5V8A2.5 2.5 0 0 1 5 5.5Z" /><path d="M8 12h.01M12 12h.01M16 12h.01" /></svg>;
  if (name === "upload") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M8 8l4-4 4 4M5 13.5v3A2.5 2.5 0 0 0 7.5 19h9a2.5 2.5 0 0 0 2.5-2.5v-3" /></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.2 2.5 2.7.4-2 2 .5 2.8-2.4-1.3-2.4 1.3.5-2.8-2-2 2.7-.4Z" /><path d="M12 12v8M7.5 20h9" /></svg>;
}

function BrandLink() {
  return (
    <Link to="/" className="brand-link" aria-label="우리사이 홈으로 이동">
      <span className="brand-mark" aria-hidden="true">♥</span>
      <span className="brand-copy">
        <span className="brand-name">우리사이</span>
        <span className="brand-tagline">대화로 기록하는 우리</span>
      </span>
    </Link>
  );
}

function AppShell() {
  const { pathname } = useLocation();
  const isOnboarding = pathname === "/onboarding";

  return (
    <div className="app-shell">
      <header className={isOnboarding ? "site-header site-header--minimal" : "site-header"}>
        <div className="site-header__inner">
          <BrandLink />
          {!isOnboarding && (
            <nav className="site-nav" aria-label="주요 메뉴">
              {navigationItems.map((item) => {
                const isActive = item.matches(pathname);
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className="nav-link"
                    aria-current={isActive ? "page" : undefined}
                  >
                    <span className="nav-link__icon"><NavIcon name={item.icon} /></span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          )}
          {!isOnboarding && (
            <span className="profile-chip" aria-label="우리 프로필">
              <span className="profile-avatar" aria-hidden="true"><i /><b /></span>
              <span className="profile-chip__name">우리</span>
              <span className="profile-chip__chevron" aria-hidden="true">⌄</span>
            </span>
          )}
        </div>
      </header>
      <div className="app-shell__content">
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route
            path="/"
            element={USE_MOCK ? <Timeline /> : <Navigate to="/onboarding" replace />}
          />
          <Route
            path="/timeline"
            element={USE_MOCK ? <Timeline /> : <Navigate to="/onboarding" replace />}
          />
          <Route path="/upload" element={<Upload />} />
          <Route
            path="/report"
            element={USE_MOCK ? <Report /> : <Navigate to="/onboarding" replace />}
          />
          <Route path="/reports/:week" element={<Report />} />
          <Route path="/review" element={<Review />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/onboarding" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return <AppShell />;
}
