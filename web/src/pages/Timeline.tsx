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

function formatWeekDate(weekStart: string): string {
  const [, month, day] = weekStart.split("-");
  return month && day ? `${Number(month)}월 ${Number(day)}일` : weekStart;
}

function topActivity(week: TimelineWeek): string {
  const weekday = week.summary.activity.top_weekday;
  const hour = week.summary.activity.top_hour;
  if (weekday === null || hour === null) return "활발한 시간 정보가 없어요";
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  return `가장 활발한 시간: ${weekdays[weekday] ?? "-"}요일 ${hour}시`;
}

function percentText(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
}

function summaryPeakHour(week: TimelineWeek): string {
  const hour = week.summary.activity.top_hour;
  return hour === null ? "-" : `${hour}시`;
}

const summaryCardMeta = [
  { label: "메시지 수", description: "이번 주에 나눈 이야기", icon: "mail", tone: "coral" },
  { label: "대화 시간", description: "세션 중앙값", icon: "clock", tone: "peach" },
  { label: "활발한 시간", description: "우리의 대화가 가장 빛난 때", icon: "sparkle", tone: "yellow" },
  { label: "대화 세션", description: "함께 이어간 대화", icon: "heart-chat", tone: "lavender" },
] as const;

type TimelineIconName = (typeof summaryCardMeta)[number]["icon"];

function TimelineIcon({ name }: { name: TimelineIconName | "calendar" }) {
  if (name === "mail") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h17v11h-17z" /><path d="m4 7 8 6 8-6" /></svg>;
  }
  if (name === "clock") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.25" /><path d="M12 7.5v4.8l3.3 2" /></svg>;
  }
  if (name === "sparkle") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></svg>;
  }
  if (name === "heart-chat") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.25 6.25h11.5a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3h-6l-3.25 2v-2h-2a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3Z" /><path d="M11.9 14.2c-2.5-1.5-3.3-2.6-2.7-3.6.5-.8 1.6-.8 2.7.2 1.1-1 2.2-1 2.7-.2.6 1-.2 2.1-2.7 3.6Z" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></svg>;
}

function EnvelopeIllustration() {
  return (
    <div className="timeline-envelope-art" aria-hidden="true">
      <span className="timeline-envelope-art__halo" />
      <span className="timeline-envelope-art__heart timeline-envelope-art__heart--one">♥</span>
      <span className="timeline-envelope-art__heart timeline-envelope-art__heart--two">♥</span>
      <span className="timeline-envelope-art__sparkle">✦</span>
      <span className="timeline-envelope-art__bubble">우리 이야기 <b>⌁</b></span>
      <span className="timeline-envelope-art__heart timeline-envelope-art__heart--three">♥</span>
      <span className="timeline-envelope-art__sparkle timeline-envelope-art__sparkle--two">✧</span>
      <svg className="timeline-envelope" viewBox="0 0 250 180" role="img" aria-label="편지와 하트가 담긴 봉투 일러스트">
        <defs>
          <linearGradient id="envelope-paper" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fffdfd" />
            <stop offset="1" stopColor="#fff2f7" />
          </linearGradient>
          <linearGradient id="envelope-flap" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffadc2" />
            <stop offset="1" stopColor="#ff78a3" />
          </linearGradient>
        </defs>
        <path d="M9 112c25-24 43-31 61-27 18 4 25 20 43 19 22-1 29-27 58-30 21-2 38 7 57 26" fill="none" stroke="#ffb3c1" strokeDasharray="3 7" strokeLinecap="round" strokeWidth="2" opacity=".62" />
        <path d="M41 57c0-8 6-14 14-14h140c8 0 14 6 14 14v82c0 8-6 14-14 14H55c-8 0-14-6-14-14Z" fill="url(#envelope-paper)" stroke="#ffb3c1" strokeWidth="3" />
        <path d="m43 61 75 56c4 3 10 3 14 0l75-56" fill="#ffe8f0" stroke="#ffb3c1" strokeWidth="3" />
        <path d="m43 139 61-51 14 11c4 3 10 3 14 0l14-11 61 51" fill="#fff4f8" stroke="#ffb3c1" strokeWidth="3" />
        <path d="M53 48h144c6 0 11 5 11 11l-65 49c-4 3-10 3-14 0L42 59c0-6 5-11 11-11Z" fill="url(#envelope-flap)" stroke="#ff9db7" strokeWidth="3" />
        <path d="M104 77h42v45h-42z" rx="4" fill="#fffdfd" stroke="#f7c0d1" strokeWidth="2" transform="rotate(-6 125 99)" />
        <path d="M125 111c-13-8-17-14-13-19 3-4 8-3 13 2 5-5 10-6 13-2 4 5 0 11-13 19Z" fill="#ff78a3" />
        <path d="M113 128h28M118 134h18" stroke="#f2bfd0" strokeLinecap="round" strokeWidth="2" />
      </svg>
    </div>
  );
}

export default function Timeline() {
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["timeline"],
    queryFn: () => api.get<TimelineResponse>(TIMELINE_PATH),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <main className="timeline-page timeline-page--state">
        <Card className="timeline-state-card">
          <p className="text-gray-600">타임라인을 불러오는 중이에요…</p>
          <div className="mt-4 h-2 animate-pulse rounded bg-gray-200" />
        </Card>
      </main>
    );
  }

  if (error) {
    return (
      <main className="timeline-page timeline-page--state">
        <Card className="timeline-state-card border-red-200 bg-red-50">
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
      <main className="timeline-page timeline-page--state">
        <h1 className="text-2xl font-bold text-gray-900">우리의 타임라인</h1>
        <Card className="timeline-state-card text-center">
          <Badge tone="neutral">아직 데이터가 없어요</Badge>
          <p className="mt-3 text-gray-600">대화 파일을 업로드하면 주차별 변화가 여기에 표시돼요.</p>
          <Link to="/upload" className="mt-4 inline-block text-sm font-medium text-rose-600 hover:underline">
            대화 파일 올리기
          </Link>
        </Card>
      </main>
    );
  }

  const currentWeek = weeks[weeks.length - 1];
  const weekGridCount = Math.min(weeks.length, 4);
  const summaryValues = [
    currentWeek.summary.message_count.toLocaleString(),
    `${currentWeek.summary.session_length_median}분`,
    summaryPeakHour(currentWeek),
    currentWeek.summary.session_count.toLocaleString(),
  ];

  return (
    <main className="timeline-page">
      <div className="timeline-background-decor" aria-hidden="true">
        <span className="timeline-cloud timeline-cloud--one" />
        <span className="timeline-cloud timeline-cloud--two" />
        <span className="timeline-bg-heart timeline-bg-heart--one">♥</span>
        <span className="timeline-bg-heart timeline-bg-heart--two">♡</span>
        <span className="timeline-bg-sparkle timeline-bg-sparkle--one">✦</span>
        <span className="timeline-bg-sparkle timeline-bg-sparkle--two">✧</span>
        <span className="timeline-flight-path" />
        <span className="timeline-petal timeline-petal--one" />
        <span className="timeline-petal timeline-petal--two" />
        <span className="timeline-petal timeline-petal--three" />
        <span className="timeline-petal timeline-petal--four" />
        <span className="timeline-edge-flower timeline-edge-flower--left"><i /><b /><em /></span>
        <span className="timeline-edge-flower timeline-edge-flower--right"><i /><b /><em /></span>
        <span className="timeline-edge-heart timeline-edge-heart--one">♡</span>
        <span className="timeline-edge-heart timeline-edge-heart--two">♥</span>
      </div>
      <header className="timeline-hero">
        <div className="timeline-hero__copy">
          <span className="timeline-eyebrow">OUR WEEKLY STORY</span>
          <h1>이번 주 우리 대화는<br /><span>어땠을까요? <em>♡</em></span></h1>
          <p>서로의 이야기가 쌓여 우리의 기록이 돼요</p>
        </div>
        <div className="timeline-hero__aside">
          <EnvelopeIllustration />
          <div className="timeline-week-pill">
            <span className="timeline-week-pill__icon"><TimelineIcon name="calendar" /></span>
            <span>{formatWeekDate(currentWeek.week_start)} 주</span>
          </div>
          {isFetching && <span className="timeline-fetching">업데이트 중</span>}
        </div>
      </header>

      <section className="timeline-summary" aria-labelledby="timeline-summary-title">
        <div className="timeline-section-heading">
          <div>
            <span className="timeline-section-kicker">A LITTLE LOOK BACK</span>
            <h2 id="timeline-summary-title">이번 주의 우리</h2>
          </div>
          <span className="timeline-section-note">최근 기록 기준</span>
        </div>
        <div className="timeline-summary-grid">
          {summaryCardMeta.map((item, index) => (
            <article key={item.label} className={`timeline-summary-card timeline-summary-card--${item.tone}`}>
              <div className="timeline-summary-card__topline">
                <span className="timeline-icon-bubble"><TimelineIcon name={item.icon} /></span>
                <span className="timeline-summary-card__label">{item.label}</span>
              </div>
              <strong className="timeline-summary-card__value">{summaryValues[index]}</strong>
              <span className="timeline-summary-card__description">{item.description}</span>
              <span className="timeline-summary-card__decor" aria-hidden="true">{index % 2 ? "✧" : "♥"}</span>
            </article>
          ))}
        </div>
      </section>

      <MetricChart weeks={weeks} />

      <section className="timeline-weeks" aria-labelledby="timeline-weeks-title">
        <div className="timeline-weeks__decor" aria-hidden="true">
          <span className="timeline-weeks__cloud timeline-weeks__cloud--left" />
          <span className="timeline-weeks__cloud timeline-weeks__cloud--right" />
          <span className="timeline-weeks__heart timeline-weeks__heart--one">♥</span>
          <span className="timeline-weeks__heart timeline-weeks__heart--two">♡</span>
          <span className="timeline-weeks__petal timeline-weeks__petal--one" />
          <span className="timeline-weeks__petal timeline-weeks__petal--two" />
          <span className="timeline-weeks__sparkle timeline-weeks__sparkle--one">✦</span>
          <span className="timeline-weeks__sparkle timeline-weeks__sparkle--two">✧</span>
        </div>
        <div className="timeline-section-heading">
          <div>
            <span className="timeline-section-kicker">OUR LITTLE ARCHIVE</span>
            <h2 id="timeline-weeks-title">주차별 우리 이야기</h2>
          </div>
          <span className="timeline-section-note">{weeks.length}개의 기록</span>
        </div>
        <div className={`timeline-week-grid timeline-week-grid--count-${weekGridCount}`}>
          {weeks.map((week) => (
            <Card key={week.week_start} className={`timeline-week-card${week.in_progress ? " timeline-week-card--progress" : ""}`}>
              <div className="timeline-week-card__header">
                <div className="timeline-week-card__date-wrap">
                  <span className="timeline-calendar"><TimelineIcon name="calendar" /></span>
                  <div>
                    <span className="timeline-week-card__overline">WEEKLY NOTE</span>
                    <Link to={`/reports/${week.week_start}`} className="timeline-week-card__date">
                      {formatWeekDate(week.week_start)}
                    </Link>
                  </div>
                </div>
                <Badge tone="neutral" className="timeline-status-badge">{reportStatusLabel(week.report_status)}</Badge>
              </div>

              <div className="timeline-week-card__metric">
                <strong>{week.summary.message_count.toLocaleString()}</strong>
                <span>messages</span>
              </div>
              <p className="timeline-week-card__activity">{topActivity(week)}</p>

              <div className="timeline-week-card__art" aria-hidden="true">
                <svg className="timeline-week-card__art-icon timeline-week-card__art-icon--envelope" viewBox="0 0 48 40">
                  <rect x="5" y="9" width="38" height="25" rx="7" fill="rgba(255,255,255,.72)" stroke="currentColor" strokeWidth="2" />
                  <path d="m7 12 15 12c1.2 1 2.8 1 4 0l15-12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="m18 22 5 4 5-4" fill="none" stroke="#ff789f" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <svg className="timeline-week-card__art-icon timeline-week-card__art-icon--sparkle" viewBox="0 0 48 40">
                  <path d="m23 3 3.2 11.8L38 18l-11.8 3.2L23 33l-3.2-11.8L8 18l11.8-3.2Z" fill="rgba(255,255,255,.7)" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                  <path d="m39 27 1.4 4.6L45 33l-4.6 1.4L39 39l-1.4-4.6L33 33l4.6-1.4Z" fill="#ffd28c" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
                <svg className="timeline-week-card__art-icon timeline-week-card__art-icon--heart" viewBox="0 0 48 40">
                  <path d="M24 34S8 25.5 8 14.8C8 8.6 15.6 5.8 20.1 11c1.6 1.9 2.9 3.1 3.9 3.1s2.3-1.2 3.9-3.1C32.4 5.8 40 8.6 40 14.8 40 25.5 24 34 24 34Z" fill="rgba(255,255,255,.68)" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                  <path d="m38 4 .9 3.1L42 8l-3.1.9L38 12l-.9-3.1L34 8l3.1-.9Z" fill="#c3a6ff" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
              </div>

              <div className="timeline-week-card__details">
                <span>우리 질문 {percentText(week.summary.question_rate.couple)}</span>
                <span>내 질문 {percentText(week.summary.question_rate.mine)}</span>
                <span>우리 답장 {week.summary.reply_gap_median_min.couple ?? "-"}분</span>
                <span>내 답장 {week.summary.reply_gap_median_min.mine ?? "-"}분</span>
              </div>

              {week.summary.sentiment && (
                <p className="timeline-week-card__sentiment">
                  좋은 말 {week.summary.sentiment.pos.length}개 · 마음 쓰인 말 {week.summary.sentiment.neg.length}개
                </p>
              )}
              {week.outlier_count > 0 && (
                <p className="timeline-week-card__notice">특별히 긴 대화 {week.outlier_count}개</p>
              )}
              {week.in_progress && <p className="timeline-week-card__notice">현재 이 주차를 정리하고 있어요</p>}

              <Link to={`/reports/${week.week_start}`} className="timeline-report-link">
                리포트 보기 <span aria-hidden="true">→</span>
              </Link>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}
