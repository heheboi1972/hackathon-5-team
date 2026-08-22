// 역할: 타임라인 — 주 단위 그래프 + 이상치 마커 (참조: FR-003, TRD §6.2) — 시여 담당
// 스캐폴딩: useTimeline 조회 + 주차 목록만. Recharts 그래프는 TODO(시여) — MetricChart.tsx 사용
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { TimelineResponse } from "../api/types";

export default function Timeline() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["timeline"],
    queryFn: () => api.get<TimelineResponse>("/api/couples/00000000-0000-0000-0000-000000000001/timeline"),
    staleTime: 30_000,
  });

  if (isLoading) return <main className="p-8">불러오는 중…</main>;
  if (error) return <main className="p-8 text-red-500">타임라인을 불러오지 못했어요.</main>;

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-2xl font-bold">우리의 타임라인</h1>
      <ul className="space-y-2">
        {data?.weeks.map((w) => (
          <li key={w.week_start} className="rounded-lg border p-4">
            <Link to={`/reports/${w.week_start}`} className="font-semibold text-rose-600 hover:underline">
              {w.week_start} 주
            </Link>
            <p className="text-sm text-gray-600">
              메시지 {w.summary.message_count}개 · 세션 {w.summary.session_count}회
              {w.outlier_count > 0 && ` · 특이 순간 ${w.outlier_count}`}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
