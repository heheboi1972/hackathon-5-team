// 역할: 주 단위 지표 LineChart + ReferenceDot 이상치 마커 (참조: TRD §2.2) — 시여 담당
// 스캐폴딩 스텁: Recharts 연결은 TODO(시여)
import type { TimelineWeek } from "../api/types";

export default function MetricChart({ weeks }: { weeks: TimelineWeek[] }) {
  return <div className="text-sm text-gray-400">MetricChart TODO — {weeks.length}주</div>;
}
