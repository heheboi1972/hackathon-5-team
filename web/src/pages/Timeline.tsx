// 역할: 타임라인 — 주 단위 지표 그래프 + 이상치 마커 (참조: FR-003, API_SPEC §4.1) — 시여 담당
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import MetricChart from "../components/MetricChart";
import type { TimelineResponse, TimelineWeek } from "../api/types";

const TIMELINE_PATH = "/api/couples/00000000-0000-0000-0000-000000000001/timeline";

function reportStatusLabel(status: TimelineWeek["report_status"]): string {
  if (status === "generated") return "생성 완료";
  if (status === "pending") return "생성 중";
  if (status === "insufficient_baseline") return "기준 데이터 부족";
  return "처리 실패";
}

function topActivity(week: TimelineWeek): string {
  const weekday = week.summary.activity.top_weekday;
  const hour = week.summary.activity.top_hour;
  if (weekday === null || hour === null) return "활동 시간대 정보가 없어요.";
  const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
  return `가장 활발한 시간: ${weekdays[weekday] ?? "-"}요일 ${hour}시`;
}

function percentText(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
}

export default function Timeline() {
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["timeline"],
    queryFn: () => api.get<TimelineResponse>(TIMELINE_PATH),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-8">
        <Card>
          <p className="text-gray-600">타임라인을 불러오는 중이에요…</p>
          <div className="mt-4 h-2 animate-pulse rounded bg-gray-200" />
        </Card>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto max-w-5xl p-8">
        <Card className="border-red-200 bg-red-50">
          <Badge tone="neutral">불러오기 실패</Badge>
          <h1 className="mt-2 text-lg font-semibold text-gray-900">타임라인을 불러오지 못했어요.</h1>
          <p className="mt-1 text-sm text-red-700">잠시 후 다시 시도해주세요.</p>
          <Button className="mt-4" onClick={() => refetch()}>다시 시도</Button>
        </Card>
      </main>
    );
  }

  const weeks = data?.weeks ?? [];
  if (weeks.length === 0) {
    return (
      <main className="mx-auto max-w-5xl space-y-4 p-8">
        <h1 className="text-2xl font-bold text-gray-900">우리의 타임라인</h1>
        <Card className="text-center">
          <Badge tone="neutral">아직 데이터가 없어요</Badge>
          <p className="mt-3 text-gray-600">대화 파일을 업로드하면 주차별 변화가 여기에 표시돼요.</p>
          <Link to="/upload" className="mt-4 inline-block text-sm font-medium text-rose-600 hover:underline">
            대화 파일 올리기
          </Link>
        </Card>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-rose-600">주차별 대화 흐름</p>
          <h1 className="text-2xl font-bold text-gray-900">우리의 타임라인</h1>
          <p className="mt-1 text-sm text-gray-600">우리의 대화 흐름과 내 활동 변화를 함께 볼 수 있어요.</p>
        </div>
        {isFetching && <span className="text-xs text-gray-500">업데이트 중…</span>}
      </header>

      <MetricChart weeks={weeks} />

      <section className="space-y-3" aria-label="주차별 타임라인">
        <h2 className="text-lg font-semibold text-gray-900">주차별 요약</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {weeks.map((week) => (
            <Card key={week.week_start} className={week.in_progress ? "border-amber-200" : undefined}>
              <div className="flex items-start justify-between gap-2">
                <Link to={`/reports/${week.week_start}`} className="font-semibold text-rose-600 hover:underline">
                  {week.week_start} 주
                </Link>
                <Badge tone="neutral">{reportStatusLabel(week.report_status)}</Badge>
              </div>
              <p className="mt-3 text-sm text-gray-700">
                메시지 {week.summary.message_count.toLocaleString()}개 · 세션 {week.summary.session_count}회
              </p>
              <p className="mt-1 text-sm text-gray-600">{topActivity(week)}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600">
                <span>우리 질문 {percentText(week.summary.question_rate.couple)}</span>
                <span>내 질문 {percentText(week.summary.question_rate.mine)}</span>
                <span>우리 답장 {week.summary.reply_gap_median_min.couple ?? "-"}분</span>
                <span>내 답장 {week.summary.reply_gap_median_min.mine ?? "-"}분</span>
              </div>
              {week.summary.sentiment && (
                <p className="mt-3 border-t pt-3 text-xs text-gray-500">
                  내 단어 · 긍정 {week.summary.sentiment.pos.length}개 · 부정 {week.summary.sentiment.neg.length}개
                </p>
              )}
              {week.outlier_count > 0 && (
                <p className="mt-2 text-xs font-medium text-orange-600">특이 순간 {week.outlier_count}개</p>
              )}
              {week.in_progress && <p className="mt-2 text-xs text-amber-700">현재 이 주차를 처리하고 있어요.</p>}
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}
