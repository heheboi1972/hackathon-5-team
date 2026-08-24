// 역할: 주 단위 지표 LineChart + 이상치 마커 (참조: API_SPEC §4.1, TRD §2.2) — 시여 담당
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Card from "./Card";
import type { CoupleMine, TimelineWeek } from "../api/types";

type MetricKey =
  | "question_rate"
  | "message_length_median"
  | "reply_gap_median_min"
  | "resume_delay_median_min";

type TimelineMetric = CoupleMine & {
  baseline_couple?: number | null;
  baseline_mine?: number | null;
};

interface MetricConfig {
  key: MetricKey;
  title: string;
  description: string;
  format: (value: number | null) => string;
  axisFormat: (value: number) => string;
}

const METRICS: MetricConfig[] = [
  {
    key: "question_rate",
    title: "질문 비율",
    description: "대화 중 질문이 차지한 비율",
    format: (value) => (value === null ? "-" : `${(value * 100).toFixed(1)}%`),
    axisFormat: (value) => `${Math.round(value * 100)}%`,
  },
  {
    key: "message_length_median",
    title: "메시지 길이 중앙값",
    description: "메시지 하나의 글자 수 중앙값",
    format: (value) => (value === null ? "-" : `${value.toFixed(1)}자`),
    axisFormat: (value) => `${Math.round(value)}자`,
  },
  {
    key: "reply_gap_median_min",
    title: "답장 간격 중앙값",
    description: "메시지 사이 답장 간격의 중앙값",
    format: (value) => (value === null ? "-" : `${value.toFixed(1)}분`),
    axisFormat: (value) => `${Math.round(value)}분`,
  },
  {
    key: "resume_delay_median_min",
    title: "대화 재개 지연 중앙값",
    description: "다음 대화가 다시 시작되기까지의 시간",
    format: (value) => (value === null ? "-" : `${value.toFixed(1)}분`),
    axisFormat: (value) => `${Math.round(value)}분`,
  },
];

function dateLabel(weekStart: string): string {
  const [, month, day] = weekStart.split("-");
  return month && day ? `${Number(month)}/${Number(day)}` : weekStart;
}

function metricValue(week: TimelineWeek, key: MetricKey): TimelineMetric {
  return week.summary[key] as TimelineMetric;
}

function MetricTooltip({
  active,
  payload,
  label,
  config,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string; value?: number | null }>;
  label?: string;
  config: MetricConfig;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded border bg-white p-3 text-xs shadow-sm">
      <p className="mb-1 font-medium text-gray-900">{label}</p>
      {payload.map((item) => (
        <p key={item.dataKey} className="text-gray-600">
          {item.dataKey === "ours" ? "우리" : "나"}: {config.format(item.value ?? null)}
        </p>
      ))}
    </div>
  );
}

function MetricPanel({ weeks, config }: { weeks: TimelineWeek[]; config: MetricConfig }) {
  const data = weeks.map((week) => {
    const metric = metricValue(week, config.key);
    return {
      weekStart: week.week_start,
      label: dateLabel(week.week_start),
      ours: metric.couple ?? null,
      mine: metric.mine ?? null,
      baselineOurs: metric.baseline_couple ?? null,
      baselineMine: metric.baseline_mine ?? null,
      outlier: week.outlier_count > 0,
    };
  });
  const hasBaseline = data.some((item) => item.baselineOurs !== null || item.baselineMine !== null);

  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-900">{config.title}</h3>
          <p className="text-xs text-gray-500">{config.description}</p>
        </div>
        <div className="flex gap-3 text-xs text-gray-600" aria-label={`${config.title} 범례`}>
          <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-rose-500" />우리</span>
          <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-sky-500" />나</span>
        </div>
      </div>
      <div className="mt-3 h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} tickLine={false} />
            <YAxis tickFormatter={config.axisFormat} tick={{ fontSize: 11 }} tickLine={false} width={46} />
            <Tooltip content={<MetricTooltip config={config} />} />
            <Line type="monotone" dataKey="ours" name="우리" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            <Line type="monotone" dataKey="mine" name="나" stroke="#0ea5e9" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            {data
              .filter((item) => item.outlier && item.ours !== null)
              .map((item) => (
                <ReferenceDot key={item.weekStart} x={item.label} y={item.ours ?? undefined} r={5} fill="#f97316" stroke="#fff" />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {hasBaseline && (
        <p className="text-xs text-gray-500">
          기준값 · 우리 {config.format(data.find((item) => item.baselineOurs !== null)?.baselineOurs ?? null)} · 나 {config.format(data.find((item) => item.baselineMine !== null)?.baselineMine ?? null)}
        </p>
      )}
    </Card>
  );
}

export default function MetricChart({ weeks }: { weeks: TimelineWeek[] }) {
  if (weeks.length === 0) return null;

  return (
    <section className="grid gap-4 lg:grid-cols-2" aria-label="주차별 지표 그래프">
      {METRICS.map((config) => <MetricPanel key={config.key} weeks={weeks} config={config} />)}
    </section>
  );
}
