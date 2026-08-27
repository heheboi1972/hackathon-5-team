import { useEffect, useRef, useState } from "react";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const monthFormatter = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "long",
});
const dateFormatter = new Intl.DateTimeFormat("ko-KR", {
  year: "numeric",
  month: "long",
  day: "numeric",
  weekday: "short",
});

function toDateValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function fromDateValue(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export interface CalendarDatePickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  rangeStart?: string;
  rangeEnd?: string;
  allowClear?: boolean;
  className?: string;
}

export default function CalendarDatePicker({
  label,
  value,
  onChange,
  min,
  max,
  rangeStart = "",
  rangeEnd = "",
  allowClear = false,
  className,
}: CalendarDatePickerProps) {
  const [open, setOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const selected = value ? fromDateValue(value) : new Date();
    return new Date(selected.getFullYear(), selected.getMonth(), 1);
  });
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const gridStart = new Date(year, month, 1 - firstDay.getDay());
  const calendarDays = Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
  const today = toDateValue(new Date());
  const todayDisabled = Boolean((min && today < min) || (max && today > max));

  const toggleCalendar = () => {
    if (!open) {
      const selected = value ? fromDateValue(value) : new Date();
      setVisibleMonth(new Date(selected.getFullYear(), selected.getMonth(), 1));
    }
    setOpen((current) => !current);
  };

  const moveMonth = (offset: number) => {
    setVisibleMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  };

  const selectDate = (nextValue: string) => {
    onChange(nextValue);
    setOpen(false);
  };

  return (
    <div className={["review-date-field", className].filter(Boolean).join(" ")} ref={pickerRef}>
      <span>{label}</span>
      <button
        type="button"
        className={`review-date-input${open ? " is-open" : ""}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`${label}: ${value ? dateFormatter.format(fromDateValue(value)) : "선택 안 됨"}. 달력 열기`}
        onClick={toggleCalendar}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="4" y="5.5" width="16" height="15" rx="2.5" />
          <path d="M8 3.5v4M16 3.5v4M4 10h16" />
        </svg>
        <strong>{value ? dateFormatter.format(fromDateValue(value)) : "날짜 선택"}</strong>
        <i aria-hidden="true" />
      </button>

      {open && (
        <div className="review-calendar" role="dialog" aria-label={`${label} 달력`}>
          <div className="review-calendar__heading">
            <button type="button" onClick={() => moveMonth(-1)} aria-label="이전 달">‹</button>
            <strong aria-live="polite">{monthFormatter.format(visibleMonth)}</strong>
            <button type="button" onClick={() => moveMonth(1)} aria-label="다음 달">›</button>
          </div>
          <div className="review-calendar__weekdays" aria-hidden="true">
            {WEEKDAYS.map((weekday) => <span key={weekday}>{weekday}</span>)}
          </div>
          <div className="review-calendar__days" role="grid">
            {calendarDays.map((date) => {
              const dateValue = toDateValue(date);
              const disabled = Boolean((min && dateValue < min) || (max && dateValue > max));
              const outsideMonth = date.getMonth() !== month;
              const selected = dateValue === value;
              const rangeEdge = dateValue === rangeStart || dateValue === rangeEnd;
              const inRange = Boolean(rangeStart && rangeEnd && dateValue >= rangeStart && dateValue <= rangeEnd);
              return (
                <button
                  key={dateValue}
                  type="button"
                  role="gridcell"
                  className={[
                    outsideMonth ? "is-outside" : "",
                    dateValue === today ? "is-today" : "",
                    inRange ? "is-in-range" : "",
                    rangeEdge ? "is-range-edge" : "",
                    selected ? "is-selected" : "",
                  ].filter(Boolean).join(" ")}
                  disabled={disabled}
                  aria-current={dateValue === today ? "date" : undefined}
                  aria-selected={selected}
                  aria-label={dateFormatter.format(date)}
                  onClick={() => selectDate(dateValue)}
                >
                  {date.getDate()}
                </button>
              );
            })}
          </div>
          <div className="review-calendar__footer">
            <span>원하는 날짜를 눌러주세요</span>
            <div className="review-calendar__footer-actions">
              {allowClear && value && (
                <button type="button" onClick={() => selectDate("")}>지우기</button>
              )}
              <button type="button" disabled={todayDisabled} onClick={() => selectDate(today)}>오늘</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
