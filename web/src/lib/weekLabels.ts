const KOREAN_WEEK_ORDINALS = ["첫째", "둘째", "셋째", "넷째", "다섯째", "여섯째"];

export function formatFriendlyWeekLabel(weekStart: string): string {
  const date = new Date(`${weekStart}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return weekStart;

  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  const firstOfMonth = new Date(Date.UTC(year, month, 1));
  const firstMonday = 1 + ((8 - firstOfMonth.getUTCDay()) % 7);
  const ordinal = Math.floor((day - firstMonday) / 7) + 1;

  return `${month + 1}월 ${KOREAN_WEEK_ORDINALS[ordinal - 1] ?? `${ordinal}번째`} 주`;
}
