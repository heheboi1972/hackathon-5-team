// 역할: 리포트 — summary/highlights/suggestions/moments (참조: FR-004, TRD §6.2) — 시여 담당
// 스캐폴딩: 조회 + 카드 나열. 디자인은 TODO(시여)
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import HighlightCard from "../components/HighlightCard";
import MomentCard from "../components/MomentCard";
import type { ReportResponse } from "../api/types";

export default function Report() {
  const { week } = useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["reports", week],
    queryFn: () =>
      api.get<ReportResponse>(`/api/couples/00000000-0000-0000-0000-000000000001/reports/${week}`),
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 3000 : false),
  });

  if (isLoading) return <main className="p-8">불러오는 중…</main>;
  if (!data) return <main className="p-8">리포트가 없어요.</main>;

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <h1 className="text-2xl font-bold">{data.week_start} 주간 리포트</h1>
      {data.status === "pending" && <p>리포트를 만드는 중이에요…</p>}
      {data.highlights.map((h) => (
        <HighlightCard
          key={h.id}
          highlight={h}
          suggestion={data.suggestions.find((s) => s.linked_highlight === h.id)}
        />
      ))}
      {data.moments.map((m, i) => (
        <MomentCard key={i} moment={m} />
      ))}
    </main>
  );
}
