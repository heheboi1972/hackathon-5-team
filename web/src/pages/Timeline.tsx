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
      <img className="timeline-home-generated-illustration" src="/home-couple-illustration-transparent.png" alt="" />
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
      <svg className="timeline-home-characters" viewBox="0 0 250 180" aria-hidden="true">
        <path d="M13 143c28-7 48-8 66-2M171 141c25-7 47-7 68 0" fill="none" stroke="#c6ace8" strokeDasharray="2 5" strokeLinecap="round" strokeWidth="2" opacity=".7" />
        <g className="timeline-home-character timeline-home-character--left" transform="translate(68 143) scale(1.15 1.3) translate(-31 -143)">
          <ellipse cx="28" cy="143" rx="18" ry="3" fill="#d98b9f" opacity=".18" />
          <path d="M12 137c5-12 8-21 16-26 8 5 14 14 18 26Z" fill="#e889a4" stroke="#a95372" strokeLinejoin="round" strokeWidth="2" />
          <path d="M17 129h27l-5 8H13Z" fill="#f7c4cf" opacity=".95" />
          <path d="M20 113c-7 2-11 8-14 14M39 113c6 3 10 8 12 14" fill="none" stroke="#a95372" strokeLinecap="round" strokeWidth="2" />
          <path d="M20 108c4-5 15-5 20 0l-2 12H22Z" fill="#fff2f4" stroke="#d47a91" strokeWidth="1.5" />
          <path d="M23 114h16M25 117h12M20 130c6-2 13-2 21 0" fill="none" stroke="#d47a91" strokeLinecap="round" strokeWidth="1.1" opacity=".8" />
          <circle cx="31" cy="99" r="8" fill="#ffd3be" stroke="#8b6370" strokeWidth="1.5" />
          <path d="M22 99c0-9 5-13 11-12 6 0 10 5 8 12l-4-4-3 4-4-4-5 5Z" fill="#30232d" />
          <path d="M39 91c5 1 7 4 7 8" fill="none" stroke="#30232d" strokeLinecap="round" strokeWidth="2.5" />
          <circle cx="28" cy="103" r="1" fill="#4f3944" /><circle cx="34" cy="103" r="1" fill="#4f3944" />
          <path d="M28 108c2 2 4 2 6 0" fill="none" stroke="#d77b8d" strokeLinecap="round" strokeWidth="1.2" />
        </g>
        <g className="timeline-home-character timeline-home-character--right" transform="translate(182 143) scale(1.15 1.3) translate(-222 -143)">
          <ellipse cx="222" cy="143" rx="18" ry="3" fill="#7195b6" opacity=".2" />
          <path d="M208 137c1-16 6-27 14-28 9 2 15 13 16 28Z" fill="#5d92a7" stroke="#3e697d" strokeLinejoin="round" strokeWidth="2" />
          <path d="M213 115h18l-4 23h-11Z" fill="#d9edf0" opacity=".95" />
          <path d="M215 115h14l-7 10Z" fill="#f6d4a4" opacity=".9" />
          <path d="M215 125h14M214 130h16M216 135h12" fill="none" stroke="#3e697d" strokeLinecap="round" strokeWidth="1.1" opacity=".8" />
          <path d="M210 120c-5 3-7 8-9 14M234 120c5 3 7 8 9 14" fill="none" stroke="#3e697d" strokeLinecap="round" strokeWidth="2" />
          <circle cx="222" cy="99" r="8" fill="#ffd3be" stroke="#8b6370" strokeWidth="1.5" />
          <path d="M211 96c2-9 7-13 13-12 8 0 12 5 12 12h-5l-3-4-4 4-5-4-4 4Z" fill="#23344c" />
          <path d="M210 94h25M214 91h17" stroke="#23344c" strokeLinecap="round" strokeWidth="2" />
          <path d="M219 103h1M225 103h1" stroke="#4f3944" strokeLinecap="round" strokeWidth="1.4" />
          <path d="M219 108c2 2 4 2 6 0" fill="none" stroke="#d77b8d" strokeLinecap="round" strokeWidth="1.2" />
        </g>
        <path d="M48 91l2 4 4 2-4 2-2 4-2-4-4-2 4-2Z" fill="#fff" opacity=".85" />
        <path d="M202 73l1.5 3 3 1.5-3 1.5-1.5 3-1.5-3-3-1.5 3-1.5Z" fill="#fff" opacity=".85" />
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
