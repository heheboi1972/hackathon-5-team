// 역할: 라우트 정의 (참조: TRD §6.1) — 가드(couples/me 분기)는 TODO(시여)
import { Navigate, Route, Routes } from "react-router-dom";
import Onboarding from "./pages/Onboarding";
import Report from "./pages/Report";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Timeline from "./pages/Timeline";
import Upload from "./pages/Upload";

export default function App() {
  return (
    <Routes>
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/" element={<Timeline />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/reports/:week" element={<Report />} />
      <Route path="/review" element={<Review />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="*" element={<Navigate to="/onboarding" replace />} />
    </Routes>
  );
}
