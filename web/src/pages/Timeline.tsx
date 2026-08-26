import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import ChatPanel from "../components/ChatPanel";
import type { CoupleMeResponse, TimelineResponse } from "../api/types";

const TIMELINE_PATH = "/api/couples/00000000-0000-0000-0000-000000000001/timeline";
const COUPLE_ME_PATH = "/api/couples/me";
const COUPLE_ID = "00000000-0000-0000-0000-000000000001";

function parseCalendarDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const date = new Date(year, month, day);
  return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day
    ? date
    : null;
}

function sameCalendarDate(left: Date, right: Date): boolean {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
}

function formatDDay(firstMetAt: string | null | undefined): string | null {
  const firstMetDate = parseCalendarDate(firstMetAt);
  if (!firstMetDate) return null;

  const today = new Date();
  const todayDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const dayDifference = Math.round(
    (todayDate.getTime() - firstMetDate.getTime()) / (24 * 60 * 60 * 1000),
  );

  if (dayDifference === 0) return "D-DAY";
  return dayDifference > 0 ? `D+${dayDifference}` : `D-${Math.abs(dayDifference)}`;
}

function MonthlyCalendar({ firstMetAt }: { firstMetAt?: string | null }) {
  const [displayedMonth, setDisplayedMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const firstMetDate = parseCalendarDate(firstMetAt);
  const today = new Date();
  const year = displayedMonth.getFullYear();
  const month = displayedMonth.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const calendarCells = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  return (
    <section className="timeline-calendar-card" aria-labelledby="timeline-calendar-title">
      <div className="timeline-calendar-card__header">
        <button
          type="button"
          className="timeline-calendar-card__nav"
          onClick={() => setDisplayedMonth(new Date(year, month - 1, 1))}
          aria-label="이전 달"
        >
          ‹
        </button>
        <h2 id="timeline-calendar-title" aria-live="polite">{year}년 {month + 1}월</h2>
        <button
          type="button"
          className="timeline-calendar-card__nav"
          onClick={() => setDisplayedMonth(new Date(year, month + 1, 1))}
          aria-label="다음 달"
        >
          ›
        </button>
      </div>
      <div className="timeline-calendar-card__weekdays" aria-hidden="true">
        {[
          ["일", "is-sunday"],
          ["월", ""],
          ["화", ""],
          ["수", ""],
          ["목", ""],
          ["금", ""],
          ["토", "is-saturday"],
        ].map(([label, tone]) => <span key={label} className={tone}>{label}</span>)}
      </div>
      <div className="timeline-calendar-card__grid">
        {calendarCells.map((day, index) => {
          if (day === null) return <span key={`empty-${index}`} aria-hidden="true" />;

          const date = new Date(year, month, day);
          const isFirstMet = firstMetDate ? sameCalendarDate(date, firstMetDate) : false;
          const isToday = sameCalendarDate(date, today);
          const className = [
            "timeline-calendar-card__day",
            index % 7 === 0 ? "is-sunday" : "",
            index % 7 === 6 ? "is-saturday" : "",
            isToday ? "is-today" : "",
            isFirstMet ? "is-first-met" : "",
          ].filter(Boolean).join(" ");
          const label = isFirstMet ? `${month + 1}월 ${day}일, 처음 만난 날` : `${month + 1}월 ${day}일`;

          return (
            <span key={day} className={className} aria-label={label}>
              {isFirstMet && <span className="timeline-calendar-card__heart" aria-hidden="true">♡</span>}
              <span>{day}</span>
            </span>
          );
        })}
      </div>
    </section>
  );
}

export default function Timeline() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["timeline"],
    queryFn: () => api.get<TimelineResponse>(TIMELINE_PATH),
    staleTime: 30_000,
  });
  const { data: coupleData } = useQuery({
    queryKey: ["couple-me"],
    queryFn: () => api.get<CoupleMeResponse>(COUPLE_ME_PATH),
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
        <h1 className="text-2xl font-bold text-gray-900"></h1>
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

  const dday = formatDDay(coupleData?.first_met_at);

  return (
    <main className="timeline-page">
      <div className="timeline-background-decor" aria-hidden="true">
        <span className="timeline-cloud timeline-cloud--one" />
        <span className="timeline-cloud timeline-cloud--two" />
        <span className="timeline-bg-sparkle timeline-bg-sparkle--one">✦</span>
        <span className="timeline-bg-sparkle timeline-bg-sparkle--two">✧</span>
        <span className="timeline-flight-path" />
        <span className="timeline-petal timeline-petal--one" />
        <span className="timeline-petal timeline-petal--two" />
        <span className="timeline-petal timeline-petal--three" />
        <span className="timeline-petal timeline-petal--four" />
        <span className="timeline-edge-flower timeline-edge-flower--left"><i /><b /><em /></span>
        <span className="timeline-edge-flower timeline-edge-flower--right"><i /><b /><em /></span>
      </div>
      <header className="timeline-home-header" aria-labelledby="timeline-home-title">
        <div className="timeline-home-header__copy">
          <span className="timeline-home-header__eyebrow"></span>
          <h1 id="timeline-home-title"></h1>
        </div>
        <div
          className={`timeline-dday${dday ? "" : " is-unset"}`}
          aria-label={`D-DAY ${dday ?? "미설정"}`}
        >
          <span className="timeline-dday__label">D-DAY</span>
          <strong>{dday ?? "미설정"}</strong>
        </div>
      </header>
      <MonthlyCalendar firstMetAt={coupleData?.first_met_at} />

      <section className="timeline-summary" aria-labelledby="timeline-summary-title">
        <div className="timeline-section-heading">
          <div>
            <span className="timeline-section-kicker">A LITTLE LOOK BACK</span>
            <h2 id="timeline-summary-title"></h2>
          </div>
          <span className="timeline-section-note">최근 기록 기준</span>
        </div>
      </section>

      <ChatPanel coupleId={COUPLE_ID} />
    </main>
  );
}
