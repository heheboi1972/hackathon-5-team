import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import ChatPanel from "../components/ChatPanel";
import { useCoupleMe } from "../hooks/useCoupleMe";
import type { TimelineResponse } from "../api/types";


function EnvelopeIllustration() {
  return (
    <div className="timeline-home-envelope-art" aria-hidden="true">
      <span className="timeline-home-envelope-art__halo" />
      <span className="timeline-home-envelope-art__heart timeline-home-envelope-art__heart--one">♥</span>
      <span className="timeline-home-envelope-art__heart timeline-home-envelope-art__heart--two">♥</span>
      <span className="timeline-home-envelope-art__sparkle">✦</span>
      <span className="timeline-home-envelope-art__bubble">우리 이야기 <b>⌁</b></span>
      <span className="timeline-home-envelope-art__heart timeline-home-envelope-art__heart--three">♥</span>
      <span className="timeline-home-envelope-art__sparkle timeline-home-envelope-art__sparkle--two">✧</span>
      <svg className="timeline-home-envelope" viewBox="0 0 250 180" role="img" aria-label="편지와 하트가 담긴 봉투 일러스트">
        <defs>
          <linearGradient id="home-envelope-paper" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fffdfd" />
            <stop offset="1" stopColor="#fff2f7" />
          </linearGradient>
          <linearGradient id="home-envelope-flap" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffadc2" />
            <stop offset="1" stopColor="#ff78a3" />
          </linearGradient>
        </defs>
        <path d="M9 112c25-24 43-31 61-27 18 4 25 20 43 19 22-1 29-27 58-30 21-2 38 7 57 26" fill="none" stroke="#ffb3c1" strokeDasharray="3 7" strokeLinecap="round" strokeWidth="2" opacity=".62" />
        <path d="M41 57c0-8 6-14 14-14h140c8 0 14 6 14 14v82c0 8-6 14-14 14H55c-8 0-14-6-14-14Z" fill="url(#home-envelope-paper)" stroke="#ffb3c1" strokeWidth="3" />
        <path d="m43 61 75 56c4 3 10 3 14 0l75-56" fill="#ffe8f0" stroke="#ffb3c1" strokeWidth="3" />
        <path d="m43 139 61-51 14 11c4 3 10 3 14 0l14-11 61 51" fill="#fff4f8" stroke="#ffb3c1" strokeWidth="3" />
        <path d="M53 48h144c6 0 11 5 11 11l-65 49c-4 3-10 3-14 0L42 59c0-6 5-11 11-11Z" fill="url(#home-envelope-flap)" stroke="#ff9db7" strokeWidth="3" />
        <path d="M104 77h42v45h-42z" rx="4" fill="#fffdfd" stroke="#f7c0d1" strokeWidth="2" transform="rotate(-6 125 99)" />
        <path d="M125 111c-13-8-17-14-13-19 3-4 8-3 13 2 5-5 10-6 13-2 4 5 0 11-13 19Z" fill="#ff78a3" />
        <path d="M113 128h28M118 134h18" stroke="#f2bfd0" strokeLinecap="round" strokeWidth="2" />
      </svg>
    </div>
  );
}

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
  const { data: coupleData } = useCoupleMe();
  const coupleId = coupleData?.couple_id;
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["timeline", coupleId],
    queryFn: () => api.get<TimelineResponse>(`/api/couples/${coupleId}/timeline`),
    enabled: Boolean(coupleId),
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
      <div className="timeline-home-layout">
        <section className="timeline-home-banner" aria-labelledby="timeline-home-banner-title">
          <div className="timeline-home-banner__copy">
            <span className="timeline-home-banner__eyebrow">칠월칠석, 우리의 이야기</span>
            <h2 id="timeline-home-banner-title">견우와 직녀처럼,<br /><span>우리의 이야기를 이어가요</span></h2>
            <p>서로의 대화가 쌓여<br />우리만의 이야기가 됩니다.</p>
          </div>
          <EnvelopeIllustration />
        </section>
        <MonthlyCalendar firstMetAt={coupleData?.first_met_at} />
      </div>

      <section className="timeline-summary" aria-labelledby="timeline-summary-title">
        <div className="timeline-section-heading">
          <div>
            <span className="timeline-section-kicker">A LITTLE LOOK BACK</span>
            <h2 id="timeline-summary-title"></h2>
          </div>
          <span className="timeline-section-note">최근 기록 기준</span>
        </div>
      </section>

      {coupleId && <ChatPanel coupleId={coupleId} />}
    </main>
  );
}
