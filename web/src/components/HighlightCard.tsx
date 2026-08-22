// 역할: 리포트 하이라이트 카드 — observation + 해석 2개 + 근거 (참조: API_SPEC §4.2) — 시여 담당
// 스캐폴딩 스텁: 디자인은 TODO(시여)
import type { Highlight } from "../api/types";

export default function HighlightCard({ highlight }: { highlight: Highlight }) {
  return <div className="rounded-lg border p-4">{highlight.observation}</div>;
}
