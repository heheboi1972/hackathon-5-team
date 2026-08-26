import {
  Area,
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
    description: "대화 중 질문이 차지하는 비율",
    format: (value) => (value === null ? "-" : `${(value * 100).toFixed(1)}%`),
    axisFormat: (value) => `${Math.round(value * 100)}%`,
  },
  {
    key: "message_length_median",
    title: "메시지 길이 중앙값",
    description: "메시지 하나에 담긴 글자 수 중앙값",
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
    description: "다음 대화를 다시 시작하기까지의 시간",
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
    <div className="timeline-chart-tooltip">
      <p className="timeline-chart-tooltip__date">{label}</p>
      {payload.filter((item, index, items) => items.findIndex((entry) => entry.dataKey === item.dataKey) === index).map((item) => (
        <p key={item.dataKey} className="timeline-chart-tooltip__row">
          <i className={`timeline-chart-tooltip__dot timeline-chart-tooltip__dot--${item.dataKey}`} />
          <span>{item.dataKey === "ours" ? "우리" : "나"}</span>
          <strong>{config.format(item.value ?? null)}</strong>
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
  const oursGradientId = `timeline-${config.key}-ours-gradient`;
  const mineGradientId = `timeline-${config.key}-mine-gradient`;

  return (
    <Card className="timeline-chart-card">
      <div className="timeline-chart-header">
        <div>
          <h3 className="timeline-chart-title">{config.title}</h3>
          <p className="timeline-chart-description">{config.description}</p>
        </div>
        <div className="timeline-chart-legend" aria-label={`${config.title} 범례`}>
          <span><i className="timeline-legend-dot timeline-legend-dot--ours" />우리</span>
          <span><i className="timeline-legend-dot timeline-legend-dot--mine" />나</span>
        </div>
      </div>
      <div className="timeline-chart-area">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={oursGradientId} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ff9fba" />
                <stop offset="100%" stopColor="#ff78a3" />
              </linearGradient>
              <linearGradient id={mineGradientId} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#d7c1ff" />
                <stop offset="100%" stopColor="#8ea7ff" />
              </linearGradient>
              <linearGradient id={`${oursGradientId}-fill`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ff78a3" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#ff78a3" stopOpacity="0.015" />
              </linearGradient>
              <linearGradient id={`${mineGradientId}-fill`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#d8c5ff" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#d8c5ff" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} strokeDasharray="2 6" stroke="#f6e7ee" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#a998a3", fontWeight: 600 }} tickLine={false} axisLine={false} />
            <YAxis tickFormatter={config.axisFormat} tick={{ fontSize: 9, fill: "#b09da8" }} tickLine={false} axisLine={false} width={42} />
            <Tooltip cursor={{ stroke: "#ffc8d7", strokeWidth: 1 }} content={<MetricTooltip config={config} />} />
            <Area type="monotone" dataKey="ours" fill={`url(#${oursGradientId}-fill)`} stroke="none" activeDot={false} connectNulls />
            <Area type="monotone" dataKey="mine" fill={`url(#${mineGradientId}-fill)`} stroke="none" activeDot={false} connectNulls />
            <Line type="monotone" dataKey="ours" name="우리" stroke={`url(#${oursGradientId})`} strokeWidth={2.5} dot={{ r: 3, fill: "#ff78a3", strokeWidth: 2, stroke: "#ffffff" }} activeDot={{ r: 5, fill: "#f26091", stroke: "#ffffff", strokeWidth: 2 }} connectNulls />
            <Line type="monotone" dataKey="mine" name="나" stroke={`url(#${mineGradientId})`} strokeWidth={2.5} dot={{ r: 3, fill: "#a97bff", strokeWidth: 2, stroke: "#ffffff" }} activeDot={{ r: 5, fill: "#8ea7ff", stroke: "#ffffff", strokeWidth: 2 }} connectNulls />
            {data
              .filter((item) => item.outlier && item.ours !== null)
              .map((item) => (
                <ReferenceDot key={item.weekStart} x={item.label} y={item.ours ?? undefined} r={5} fill="#ffb3c1" stroke="#ffffff" strokeWidth={2} />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {hasBaseline && (
        <p className="timeline-chart-baseline">
          기준값 <span /> 우리 {config.format(data.find((item) => item.baselineOurs !== null)?.baselineOurs ?? null)} · 나 {config.format(data.find((item) => item.baselineMine !== null)?.baselineMine ?? null)}
        </p>
      )}
    </Card>
  );
}

export default function MetricChart({ weeks }: { weeks: TimelineWeek[] }) {
  if (weeks.length === 0) return null;

  return (
    <section className="timeline-chart-grid" aria-label="주차별 지표 차트">
      {METRICS.map((config) => <MetricPanel key={config.key} weeks={weeks} config={config} />)}
    </section>
  );
}
