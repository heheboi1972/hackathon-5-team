// 역할: 라우트 정의 (참조: TRD §6.1) — 가드(couples/me 분기)는 TODO(시여)
import { Link, Navigate, Route, Routes } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import Onboarding from "./pages/Onboarding";
import Report from "./pages/Report";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Timeline from "./pages/Timeline";
import Upload from "./pages/Upload";

const USE_MOCK =
  import.meta.env.VITE_USE_MOCK === "true" || import.meta.env.USE_MOCK === "true";

export default function App() {
  return (
    <>
      <nav className="border-b bg-white" aria-label="주요 메뉴">
        <div className="mx-auto flex max-w-5xl flex-wrap gap-x-4 gap-y-2 px-4 py-3 text-sm sm:px-8">
          <Link to="/onboarding" className="font-medium text-rose-600 hover:underline">온보딩</Link>
          <Link to="/upload" className="text-gray-600 hover:text-rose-600">업로드</Link>
          <Link to="/timeline" className="text-gray-600 hover:text-rose-600">타임라인</Link>
          <Link to="/reports/2026-08-17" className="text-gray-600 hover:text-rose-600">리포트</Link>
          <Link to="/review" className="text-gray-600 hover:text-rose-600">리뷰</Link>
          <Link to="/chat" className="text-gray-600 hover:text-rose-600">챗봇</Link>
          <Link to="/settings" className="text-gray-600 hover:text-rose-600">설정</Link>
        </div>
      </nav>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/" element={USE_MOCK ? <Timeline /> : <Navigate to="/onboarding" replace />} />
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
    </>
  );
}
