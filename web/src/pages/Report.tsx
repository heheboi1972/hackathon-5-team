import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import HighlightCard from "../components/HighlightCard";
import MomentCard from "../components/MomentCard";
import type { ReportResponse, TermCount, WeekSummary } from "../api/types";

const COUPLE_ID = "00000000-0000-0000-0000-000000000001";
const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

function formatWeekTitle(weekStart: string): string {
  const [year, month, day] = weekStart.split("-");
  return year && month && day
    ? `${year}년 ${Number(month)}월 ${Number(day)}일 주간 리포트`
    : `${weekStart} 주간 리포트`;
}

function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (value < 60) return `${Math.round(value)}분`;
  const hours = Math.floor(value / 60);
  const minutes = Math.round(value % 60);
  return minutes === 0 ? `${hours}시간` : `${hours}시간 ${minutes}분`;
}

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
}

function formatCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toLocaleString();
}

function hourLabel(hour: number | null): string {
  if (hour === null) return "활동 시간대 정보가 없어요.";
  if (hour === 0) return "자정 12시";
  if (hour === 12) return "낮 12시";
  return hour < 12 ? `오전 ${hour}시` : `오후 ${hour - 12}시`;
}

function statusLabel(status: ReportResponse["status"]): string {
  if (status === "generated") return "생성 완료";
  if (status === "pending") return "생성 중";
  if (status === "insufficient_baseline") return "기준 데이터 부족";
  return "처리 실패";
}

function statusMessage(status: ReportResponse["status"]): string {
  if (status === "pending") return "본문을 준비하고 있어요. 잠시 후 자동으로 업데이트됩니다.";
  if (status === "insufficient_baseline") return "비교할 기준 데이터가 아직 부족해요. 이번 주 요약은 먼저 확인할 수 있어요.";
  if (status === "failed") return "리포트를 만들지 못했어요. 잠시 후 다시 시도해주세요.";
  return "";
}

function SummaryMetric({
  label,
  couple,
  mine,
  format = formatCount,
}: {
  label: string;
  couple: number | null | undefined;
  mine: number | null | undefined;
  format?: (value: number | null | undefined) => string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-gray-900">{format(couple)}</p>
      <p className="mt-1 text-xs text-gray-500">
        {mine === undefined ? "커플 합산" : `나 ${format(mine)}`}
      </p>
    </div>
  );
}

function ActivityCard({ activity }: { activity: WeekSummary["activity"] }) {
  const weekdayMax = Math.max(...activity.by_weekday, 0);
  const hourMax = Math.max(...activity.by_hour, 0);
  const weekday = activity.top_weekday === null ? null : WEEKDAYS[activity.top_weekday] ?? null;
  const topTime = weekday && activity.top_hour !== null
    ? `${weekday}요일 ${hourLabel(activity.top_hour)}`
    : "활동 시간대 정보가 없어요.";

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-rose-600">대화 리듬</p>
          <h2 className="mt-1 text-lg font-semibold text-gray-900">활발한 시간</h2>
        </div>
        <span className="rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">{topTime}</span>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>요일별 메시지</span>
          <span>커플 합산</span>
        </div>
        <div className="mt-3 grid grid-cols-7 gap-2" aria-label="요일별 메시지 수">
          {activity.by_weekday.map((count, index) => (
            <div key={WEEKDAYS[index]} className="flex min-w-0 flex-col items-center gap-1">
              <div className="flex h-20 w-full items-end justify-center rounded bg-gray-50 px-1">
                <div
                  className="w-full rounded-t bg-rose-400"
                  style={{ height: `${weekdayMax ? Math.max((count / weekdayMax) * 100, 4) : 0}%` }}
                  title={`${WEEKDAYS[index]}요일 ${count}개`}
                />
              </div>
              <span className="text-xs text-gray-500">{WEEKDAYS[index]}</span>
              <span className="text-[11px] text-gray-400">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 border-t pt-4">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>시간대별 메시지</span>
          <span>0시 → 23시</span>
        </div>
        <div className="mt-3 flex h-20 items-end gap-1" aria-label="시간대별 메시지 수">
          {activity.by_hour.map((count, hour) => (
            <div key={hour} className="group flex h-full min-w-0 flex-1 items-end" title={`${hour}시 ${count}개`}>
              <div
                className="w-full rounded-t bg-sky-400 transition-colors group-hover:bg-sky-500"
                style={{ height: `${hourMax ? Math.max((count / hourMax) * 100, 4) : 0}%` }}
              />
            </div>
          ))}
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-gray-400">
          <span>0시</span>
          <span>6시</span>
          <span>12시</span>
          <span>18시</span>
          <span>23시</span>
        </div>
      </div>
    </Card>
  );
}

function TermGroup({ title, terms, tone }: { title: string; terms: TermCount[]; tone: "positive" | "negative" }) {
  return (
    <div>
      <p className="text-sm font-medium text-gray-700">{title}</p>
      {terms.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {terms.map((term) => (
            <span
              key={term.canonical}
              className={[
                "rounded-full px-3 py-1.5 text-sm",
                tone === "positive" ? "bg-rose-50 text-rose-700" : "bg-sky-50 text-sky-700",
              ].join(" ")}
            >
              {term.canonical} <span className="font-semibold">{term.count}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-gray-400">표시할 단어가 없어요.</p>
      )}
    </div>
  );
}

function MyTermsCard({ sentiment }: { sentiment: WeekSummary["sentiment"] }) {
  return (
    <Card>
      <p className="text-sm font-medium text-sky-600">나의 대화 습관</p>
      <h2 className="mt-1 text-lg font-semibold text-gray-900">내 단어</h2>
      <p className="mt-1 text-sm text-gray-500">이번 주 내가 자주 사용한 긍정·부정 단어예요.</p>
      {sentiment ? (
        <div className="mt-5 space-y-5">
          <TermGroup title="긍정 단어" terms={sentiment.pos} tone="positive" />
          <TermGroup title="부정 단어" terms={sentiment.neg} tone="negative" />
        </div>
      ) : (
        <p className="mt-5 rounded-lg bg-gray-50 p-4 text-sm text-gray-500">
          아직 단어 사전이 준비되지 않았어요.
        </p>
      )}
    </Card>
  );
}

export default function Report() {
  const { week: routeWeek } = useParams();
  const week = routeWeek ?? "2026-08-17";
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["reports", week],
    queryFn: () =>
      api.get<ReportResponse>(`/api/couples/${COUPLE_ID}/reports/${week}`),
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 3000 : false),
  });

  if (isLoading) {
    return (
      <main className="mx-auto max-w-4xl space-y-4 p-6 sm:p-8">
        <Card>
          <p className="text-gray-600">주간 리포트를 불러오는 중이에요…</p>
          <div className="mt-4 h-2 animate-pulse rounded bg-gray-200" />
        </Card>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="mx-auto max-w-4xl p-6 sm:p-8">
        <Card className="border-red-200 bg-red-50">
          <Badge>불러오기 실패</Badge>
          <h1 className="mt-2 text-lg font-semibold text-gray-900">리포트를 불러오지 못했어요.</h1>
          <p className="mt-1 text-sm text-red-700">잠시 후 다시 시도해주세요.</p>
          <Button className="mt-4" onClick={() => refetch()}>다시 시도</Button>
        </Card>
      </main>
    );
  }

  const summary = data.summary ?? null;
  const linkedHighlightIds = new Set(data.highlights.map((highlight) => highlight.id));
  const additionalSuggestions = data.suggestions.filter(
    (suggestion) => !linkedHighlightIds.has(suggestion.linked_highlight),
  );

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 sm:p-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/timeline" className="text-sm font-medium text-rose-600 hover:underline">← 타임라인으로</Link>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-gray-500">커플 대화 리포트</p>
            <Badge tone={data.status === "failed" ? "neutral" : data.status === "pending" ? "b" : "neutral"}>
              {statusLabel(data.status)}
            </Badge>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">{formatWeekTitle(data.week_start)}</h1>
          {isFetching && data.status !== "pending" && <p className="mt-1 text-xs text-gray-500">업데이트 중…</p>}
        </div>
      </header>

      {statusMessage(data.status) && (
        <Card className={data.status === "failed" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}>
          <p className={data.status === "failed" ? "text-sm text-red-700" : "text-sm text-amber-800"}>
            {statusMessage(data.status)}
          </p>
        </Card>
      )}

      {summary && (
        <>
          <section aria-labelledby="summary-title">
            <div className="mb-3">
              <h2 id="summary-title" className="text-lg font-semibold text-gray-900">이번 주 한눈에 보기</h2>
              <p className="mt-1 text-sm text-gray-500">우리와 내 대화 흐름을 함께 살펴봤어요.</p>
            </div>
            <Card>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <SummaryMetric label="대화 세션" couple={summary.session_count} mine={undefined} />
                <SummaryMetric label="메시지" couple={summary.message_count} mine={undefined} />
                <SummaryMetric
                  label="질문 비율"
                  couple={summary.question_rate.couple}
                  mine={summary.question_rate.mine}
                  format={formatPercent}
                />
                <SummaryMetric
                  label="답장 간격 중앙값"
                  couple={summary.reply_gap_median_min.couple}
                  mine={summary.reply_gap_median_min.mine}
                  format={formatMinutes}
                />
              </div>
              <div className="mt-3 grid gap-3 border-t pt-3 sm:grid-cols-3">
                <SummaryMetric
                  label="메시지 길이 중앙값"
                  couple={summary.message_length_median.couple}
                  mine={summary.message_length_median.mine}
                  format={(value) => value === null || value === undefined ? "-" : `${value.toFixed(1)}자`}
                />
                <SummaryMetric
                  label="대화 재개 지연"
                  couple={summary.resume_delay_median_min.couple}
                  mine={summary.resume_delay_median_min.mine}
                  format={formatMinutes}
                />
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-500">세션 길이 중앙값</p>
                  <p className="mt-1 text-lg font-semibold text-gray-900">{formatMinutes(summary.session_length_median)}</p>
                  <p className="mt-1 text-xs text-gray-500">우리 대화 기준</p>
                </div>
              </div>
            </Card>
          </section>

          <section className="grid gap-4 lg:grid-cols-2" aria-label="활동과 내 단어">
            <ActivityCard activity={summary.activity} />
            <MyTermsCard sentiment={summary.sentiment} />
          </section>
        </>
      )}

      {data.highlights.length > 0 && (
        <section aria-labelledby="highlights-title">
          <div className="mb-3">
            <h2 id="highlights-title" className="text-lg font-semibold text-gray-900">이번 주의 발견</h2>
            <p className="mt-1 text-sm text-gray-500">대화 흐름에서 눈여겨볼 만한 점을 정리했어요.</p>
          </div>
          <div className="space-y-3">
            {data.highlights.map((highlight) => (
              <HighlightCard
                key={highlight.id}
                highlight={highlight}
                suggestion={data.suggestions.find((suggestion) => suggestion.linked_highlight === highlight.id)}
              />
            ))}
          </div>
        </section>
      )}

      {additionalSuggestions.length > 0 && (
        <section aria-labelledby="suggestions-title">
          <h2 id="suggestions-title" className="mb-3 text-lg font-semibold text-gray-900">이번 주 제안</h2>
          <div className="space-y-3">
            {additionalSuggestions.map((suggestion) => (
              <Card key={suggestion.id} className="border-rose-100 bg-rose-50/50">
                <p className="text-sm text-rose-800">{suggestion.text}</p>
              </Card>
            ))}
          </div>
        </section>
      )}

      {data.moments.length > 0 && (
        <section aria-labelledby="moments-title">
          <div className="mb-3">
            <h2 id="moments-title" className="text-lg font-semibold text-gray-900">기억해둘 순간</h2>
            <p className="mt-1 text-sm text-gray-500">평소와 달랐던 대화의 순간이에요.</p>
          </div>
          <div className="space-y-3">
            {data.moments.map((moment, index) => (
              <MomentCard key={`${moment.session_id}-${moment.at}-${index}`} moment={moment} />
            ))}
          </div>
        </section>
      )}

      {!summary && data.highlights.length === 0 && data.moments.length === 0 && data.suggestions.length === 0 && (
        <Card className="text-center">
          <p className="text-gray-600">아직 표시할 리포트 내용이 없어요.</p>
        </Card>
      )}
    </main>
  );
}
