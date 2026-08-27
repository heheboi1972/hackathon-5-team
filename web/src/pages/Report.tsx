import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import HighlightCard from "../components/HighlightCard";
import MomentCard from "../components/MomentCard";
import { useCoupleMe } from "../hooks/useCoupleMe";
import type { ReportResponse, TermCount, TimelineResponse, TimelineWeek, WeekSummary } from "../api/types";
import { formatFriendlyWeekLabel } from "../lib/weekLabels";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
function formatShortWeekDate(weekStart: string): string {
  const [year, month, day] = weekStart.split("-");
  return year && month && day
    ? `${year}년 ${Number(month)}월 ${Number(day)}일 시작`
    : weekStart;
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

function formatMomentAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
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

function WeekSelectorItem({ week, selected }: { week: TimelineWeek; selected: boolean }) {
  return (
    <Link
      to={`/reports/${week.week_start}`}
      className={`report-week-selector__item${selected ? " is-selected" : ""}`}
      aria-current={selected ? "page" : undefined}
    >
      <span className="report-week-selector__item-label">{formatFriendlyWeekLabel(week.week_start)}</span>
      <span className="report-week-selector__item-date">{formatShortWeekDate(week.week_start)}</span>
      <span className="report-week-selector__item-summary">
        메시지 {formatCount(week.summary.message_count)} · 세션 {formatCount(week.summary.session_count)}
      </span>
      <Badge tone={week.report_status === "pending" ? "b" : "neutral"}>{statusLabel(week.report_status)}</Badge>
    </Link>
  );
}

type ReportIconName = "mail" | "clock" | "sparkle" | "heart" | "quote" | "check" | "calendar";

function ReportIcon({ name }: { name: ReportIconName }) {
  if (name === "mail") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h17v11h-17z" /><path d="m4 7 8 6 8-6" /></svg>;
  }
  if (name === "clock") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.25" /><path d="M12 7.5v4.8l3.3 2" /></svg>;
  }
  if (name === "sparkle") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></svg>;
  }
  if (name === "heart") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.2S4 15.6 4 9.9C4 6.3 8.2 4.5 10.6 7c.7.7 1.1 1.4 1.4 2 .3-.6.7-1.3 1.4-2C15.8 4.5 20 6.3 20 9.9c0 5.7-8 10.3-8 10.3Z" /></svg>;
  }
  if (name === "quote") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7.5h5.5v5H8.4c.1 2 1.1 3.3 3.1 4v1.5C7.7 17.5 6 15.1 6 11.5zM13.5 7.5H19v5h-3.1c.1 2 1.1 3.3 3.1 4v1.5c-3.8-.5-5.5-2.9-5.5-6.5z" /></svg>;
  }
  if (name === "check") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="m8 12.2 2.6 2.6 5.5-5.6" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></svg>;
}

function SummaryMetric({
  label,
  couple,
  mine,
  format = formatCount,
  icon,
}: {
  label: string;
  couple: number | null | undefined;
  mine: number | null | undefined;
  format?: (value: number | null | undefined) => string;
  icon: ReportIconName;
}) {
  return (
    <article className="report-metric-card">
      <div className="report-metric-card__topline">
        <span className="report-icon-bubble"><ReportIcon name={icon} /></span>
        <p>{label}</p>
      </div>
      <p className="report-metric-card__value">{format(couple)}</p>
      <p className="report-metric-card__detail">{mine === undefined ? "커플 합산" : `나 ${format(mine)}`}</p>
    </article>
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
    <Card className="report-card report-activity-card">
      <div className="report-card-heading">
        <div>
          <p className="report-card-eyebrow">대화 리듬</p>
          <h2>활발한 시간</h2>
        </div>
        <span className="report-activity-card__icon"><ReportIcon name="clock" /></span>
      </div>
      <div className="report-activity-card__peak">
        <span>우리의 대화가 가장 반짝인 때</span>
        <strong>{topTime}</strong>
      </div>

      <div className="report-chart-block">
        <div className="report-chart-labels"><span>요일별 메시지</span><span>커플 합산</span></div>
        <div className="report-weekday-chart" aria-label="요일별 메시지 수">
          {activity.by_weekday.map((count, index) => (
            <div key={WEEKDAYS[index]} className="report-weekday-chart__item">
              <div className="report-weekday-chart__bar-wrap">
                <div
                  className="report-weekday-chart__bar"
                  style={{ height: `${weekdayMax ? Math.max((count / weekdayMax) * 100, 4) : 0}%` }}
                  title={`${WEEKDAYS[index]}요일 ${count}개`}
                />
              </div>
              <span>{WEEKDAYS[index]}</span>
              <small>{count}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="report-chart-block report-chart-block--hours">
        <div className="report-chart-labels"><span>시간대별 메시지</span><span>0시 → 23시</span></div>
        <div className="report-hour-chart" aria-label="시간대별 메시지 수">
          {activity.by_hour.map((count, hour) => (
            <div key={hour} className="report-hour-chart__item" title={`${hour}시 ${count}개`}>
              <div className="report-hour-chart__bar" style={{ height: `${hourMax ? Math.max((count / hourMax) * 100, 4) : 0}%` }} />
            </div>
          ))}
        </div>
        <div className="report-hour-chart__labels"><span>0시</span><span>6시</span><span>12시</span><span>18시</span><span>23시</span></div>
      </div>
    </Card>
  );
}

function TermGroup({ title, terms, tone }: { title: string; terms: TermCount[]; tone: "positive" | "negative" }) {
  return (
    <div className={`report-term-group report-term-group--${tone}`}>
      <p>{title}</p>
      {terms.length > 0 ? (
        <div className="report-term-list">
          {terms.map((term) => (
            <span key={term.canonical} className="report-term-chip">
              {term.canonical} <b>{term.count}</b>
            </span>
          ))}
        </div>
      ) : (
        <p className="report-empty-copy">표시할 단어가 없어요.</p>
      )}
    </div>
  );
}

function MyTermsCard({ sentiment }: { sentiment: WeekSummary["sentiment"] }) {
  return (
    <Card className="report-card report-terms-card">
      <div className="report-card-heading">
        <div>
          <p className="report-card-eyebrow report-card-eyebrow--lavender">나의 대화 습관</p>
          <h2>내 단어</h2>
        </div>
        <span className="report-activity-card__icon report-activity-card__icon--lavender"><ReportIcon name="heart" /></span>
      </div>
      <p className="report-card-description">이번 주 내가 자주 사용한 긍정·부정 단어예요.</p>
      {sentiment ? (
        <div className="report-term-groups">
          <TermGroup title="긍정 단어" terms={sentiment.pos} tone="positive" />
          <TermGroup title="부정 단어" terms={sentiment.neg} tone="negative" />
        </div>
      ) : (
        <p className="report-empty-panel">아직 단어 사전이 준비되지 않았어요.</p>
      )}
    </Card>
  );
}

export default function Report() {
  const { week: routeWeek } = useParams();
  const { data: coupleData } = useCoupleMe();
  const coupleId = coupleData?.couple_id;
  const timelineQuery = useQuery({
    queryKey: ["timeline", coupleId],
    queryFn: () => api.get<TimelineResponse>(`/api/couples/${coupleId}/timeline`),
    enabled: Boolean(coupleId),
    staleTime: 30_000,
  });
  const timelineWeeks = timelineQuery.data?.weeks ?? [];
  const latestWeek = timelineWeeks[timelineWeeks.length - 1]?.week_start;
  const routeWeekIsValid = routeWeek
    ? timelineWeeks.some((timelineWeek) => timelineWeek.week_start === routeWeek)
    : true;
  const week = routeWeekIsValid ? routeWeek ?? latestWeek : undefined;
  const reportQuery = useQuery({
    queryKey: ["reports", coupleId, week],
    queryFn: () =>
      api.get<ReportResponse>(`/api/couples/${coupleId}/reports/${week}`),
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 3000 : false),
    enabled: timelineQuery.isSuccess && Boolean(coupleId) && Boolean(week),
  });

  if (timelineQuery.isPending || (!routeWeek && timelineQuery.isFetching)) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card">
          <p>주간 리포트를 불러오는 중이에요…</p>
          <div className="report-loading-line" />
        </Card>
      </main>
    );
  }

  if (timelineQuery.error && !routeWeek) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card report-state-card--error">
          <Badge>불러오기 실패</Badge>
          <h1>주간 기록을 확인하지 못했어요.</h1>
          <p>잠시 후 다시 시도해주세요.</p>
          <Button className="report-retry-button" onClick={() => void timelineQuery.refetch()}>다시 시도</Button>
        </Card>
      </main>
    );
  }

  if (timelineQuery.isSuccess && !week) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card">
          <Badge tone="neutral">아직 기록이 없어요</Badge>
          <h1>표시할 주간 리포트가 없어요.</h1>
          <p>대화 파일을 업로드하면 주간 리포트가 준비돼요.</p>
        </Card>
      </main>
    );
  }

  if (routeWeek && timelineQuery.isSuccess && !routeWeekIsValid) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card report-state-card--error">
          <Badge>주차를 찾을 수 없음</Badge>
          <h1>해당 주간 리포트를 찾지 못했어요.</h1>
          <p>사용 가능한 주차를 선택해주세요.</p>
        </Card>
      </main>
    );
  }

  const { data, isLoading, error, refetch } = reportQuery;
  if (isLoading) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card">
          <p>주간 리포트를 불러오는 중이에요…</p>
          <div className="report-loading-line" />
        </Card>
      </main>
    );
  }

  if (error || !data || !week) {
    return (
      <main className="report-page report-page--state">
        <Card className="report-state-card report-state-card--error">
          <Badge>불러오기 실패</Badge>
          <h1>리포트를 불러오지 못했어요.</h1>
          <p>잠시 후 다시 시도해주세요.</p>
          <Button className="report-retry-button" onClick={() => refetch()}>다시 시도</Button>
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
    <main className="report-page">
      <div className="report-layout">
        <aside className="report-week-selector" aria-labelledby="report-week-selector-title">
          <div className="report-week-selector__heading">
            <span className="report-section-kicker">WEEKLY ARCHIVE</span>
            <h2 id="report-week-selector-title">우리의 지난 기록</h2>
            <p>살펴보고 싶은 주를 골라보세요.</p>
          </div>
          {timelineWeeks.length > 0 && (
            <nav className="report-week-selector__list" aria-label="주간 리포트 선택">
              {timelineWeeks.map((timelineWeek) => (
                <WeekSelectorItem
                  key={timelineWeek.week_start}
                  week={timelineWeek}
                  selected={timelineWeek.week_start === week}
                />
              ))}
            </nav>
          )}
        </aside>

        <div className="report-content">
      {statusMessage(data.status) && (
        <Card className={`report-status-card ${data.status === "failed" ? "report-status-card--error" : "report-status-card--notice"}`}>
          <span className="report-status-card__icon"><ReportIcon name="sparkle" /></span>
          <p>{statusMessage(data.status)}</p>
        </Card>
      )}

      {summary && (
        <>
          <section className="report-section report-summary-section" aria-labelledby="summary-title">
            <div className="report-section-heading">
              <div><span className="report-section-kicker">A LITTLE LOOK BACK</span><h2 id="summary-title">이번 주 우리 이야기</h2></div>
              <span className="report-section-note">대화 기록을 살펴봤어요</span>
            </div>
            <Card className="report-letter-card">
              <div className="report-letter-card__heading"><span className="report-letter-card__icon"><ReportIcon name="mail" /></span><div><p>이번 주의 기록</p><h3>서로의 마음이 오간 시간이에요</h3></div></div>
              <p className="report-letter-card__copy">우리와 내 대화 흐름을 함께 살펴봤어요.</p>
              <div className="report-metric-grid">
                <SummaryMetric label="대화 세션" couple={summary.session_count} mine={undefined} icon="mail" />
                <SummaryMetric label="메시지" couple={summary.message_count} mine={undefined} icon="heart" />
                <SummaryMetric label="질문 비율" couple={summary.question_rate.couple} mine={summary.question_rate.mine} format={formatPercent} icon="quote" />
                <SummaryMetric label="답장 간격 중앙값" couple={summary.reply_gap_median_min.couple} mine={summary.reply_gap_median_min.mine} format={formatMinutes} icon="clock" />
                <SummaryMetric label="메시지 길이 중앙값" couple={summary.message_length_median.couple} mine={summary.message_length_median.mine} format={(value) => value === null || value === undefined ? "-" : `${value.toFixed(1)}자`} icon="sparkle" />
                <SummaryMetric label="대화 재개 지연" couple={summary.resume_delay_median_min.couple} mine={summary.resume_delay_median_min.mine} format={formatMinutes} icon="heart" />
                <SummaryMetric label="세션 길이 중앙값" couple={summary.session_length_median} mine={undefined} format={formatMinutes} icon="clock" />
              </div>
            </Card>
          </section>

          <section className="report-support-grid" aria-label="활동과 내 단어">
            <ActivityCard activity={summary.activity} />
            <MyTermsCard sentiment={summary.sentiment} />
          </section>
        </>
      )}

      {data.highlights.length > 0 && (
        <section className="report-section" aria-labelledby="highlights-title">
          <div className="report-section-heading"><div><span className="report-section-kicker">LITTLE THINGS WE NOTICED</span><h2 id="highlights-title">이번 주의 발견</h2></div><span className="report-section-note">대화 속 작은 반짝임</span></div>
          <div className="report-highlight-grid">
            {data.highlights.map((highlight) => (
              <div className="report-highlight-card" key={highlight.id}>
                <span className="report-highlight-card__icon"><ReportIcon name="sparkle" /></span>
                <HighlightCard highlight={highlight} suggestion={data.suggestions.find((suggestion) => suggestion.linked_highlight === highlight.id)} />
              </div>
            ))}
          </div>
        </section>
      )}

      {additionalSuggestions.length > 0 && (
        <section className="report-section" aria-labelledby="suggestions-title">
          <div className="report-section-heading"><div><span className="report-section-kicker">A LITTLE NOTE FOR NEXT WEEK</span><h2 id="suggestions-title">다음 주 우리에게</h2></div><span className="report-section-note">천천히 함께 해봐요</span></div>
          <div className="report-suggestion-grid">
            {additionalSuggestions.map((suggestion) => (
              <Card key={suggestion.id} className="report-suggestion-card"><span className="report-suggestion-card__icon"><ReportIcon name="check" /></span><p>{suggestion.text}</p></Card>
            ))}
          </div>
        </section>
      )}

      {data.moments.length > 0 && (
        <section className="report-section" aria-labelledby="moments-title">
          <div className="report-section-heading"><div><span className="report-section-kicker">MEMORIES TO KEEP</span><h2 id="moments-title">기억하고 싶은 순간</h2></div><span className="report-section-note">우리만의 작은 장면</span></div>
          <div className="report-moments-list">
            {data.moments.map((moment, index) => (
              <article className="report-moment-card" key={`${moment.session_id}-${moment.at}-${index}`}>
                <div className="report-moment-card__rail"><span><ReportIcon name="quote" /></span></div>
                <div className="report-moment-card__body"><div className="report-moment-card__meta"><time dateTime={moment.at}>{formatMomentAt(moment.at)}</time><span>SESSION {moment.session_id}</span></div><MomentCard moment={moment} /></div>
              </article>
            ))}
          </div>
        </section>
      )}

      {!summary && data.highlights.length === 0 && data.moments.length === 0 && data.suggestions.length === 0 && (
        <Card className="report-empty-state"><span className="report-empty-state__icon"><ReportIcon name="mail" /></span><p>아직 표시할 리포트 내용이 없어요.</p></Card>
      )}
        </div>
      </div>
    </main>
  );
}
