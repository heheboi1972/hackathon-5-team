// 역할: 돌아보기 — 구간 선택 → 지표 vs 기준선 → 메모 (참조: FR-005, API_SPEC §5)
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent, type UIEvent } from "react";
import { ApiClientError, api, IS_LOCAL_MOCK } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import CalendarDatePicker from "../components/CalendarDatePicker";
import Card from "../components/Card";
import Modal from "../components/Modal";
import { useCoupleMe } from "../hooks/useCoupleMe";
import type {
  BaselineMetrics,
  CoupleMine,
  NoteCreateRequest,
  NoteResponse,
  RangeMetrics,
  ReviewResponse,
  ReviewSessionMessagesResponse,
} from "../api/types";

const SESSION_BATCH_SIZE = 15;
const MESSAGE_PAGE_SIZE = 30;


function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getInitialRange(): { start: string; end: string } {
  if (IS_LOCAL_MOCK) {
    return { start: "2026-08-17", end: "2026-08-19" };
  }

  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 6);
  return { start: toDateInputValue(start), end: toDateInputValue(end) };
}

function toIsoStart(date: string): string {
  return `${date}T00:00:00+09:00`;
}

function toIsoEnd(date: string): string {
  return `${date}T23:59:59+09:00`;
}

function getRangeError(start: string, end: string): string | null {
  if (!start || !end) return "조회할 시작일과 종료일을 모두 선택해주세요.";
  if (start > end) return "종료일은 시작일보다 빠를 수 없어요.";

  const startTime = Date.parse(`${start}T00:00:00Z`);
  const endTime = Date.parse(`${end}T00:00:00Z`);
  if (endTime - startTime > 14 * 24 * 60 * 60 * 1000) {
    return "돌아보기 범위는 최대 14일까지 선택할 수 있어요.";
  }
  return null;
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${(value * 100).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%`;
}

function formatMinutes(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}분`;
}

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${Math.round(value).toLocaleString("ko-KR")}개`;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function formatSessionDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function formatSessionTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function formatDateRange(start: string, end: string): string {
  const formatter = new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "Asia/Seoul",
  });
  return `${formatter.format(new Date(start))} ~ ${formatter.format(new Date(end))}`;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.code === "VALIDATION_ERROR") return error.message;
  return error instanceof Error ? error.message : "요청을 처리하지 못했어요.";
}

type ReviewIconName = "calendar" | "heart-chat" | "clock" | "mail" | "sparkle" | "quote" | "pencil" | "notebook";

function ReviewIcon({ name }: { name: ReviewIconName }) {
  if (name === "calendar") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></svg>;
  }
  if (name === "heart-chat") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.25 6.25h11.5a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3h-6l-3.25 2v-2h-2a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3Z" /><path d="M11.9 14.2c-2.5-1.5-3.3-2.6-2.7-3.6.5-.8 1.6-.8 2.7.2 1.1-1 2.2-1 2.7-.2.6 1-.2 2.1-2.7 3.6Z" /></svg>;
  }
  if (name === "clock") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.25" /><path d="M12 7.5v4.8l3.3 2" /></svg>;
  }
  if (name === "mail") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h17v11h-17z" /><path d="m4 7 8 6 8-6" /></svg>;
  }
  if (name === "sparkle") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></svg>;
  }
  if (name === "quote") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7.5h5.5v5H8.4c.1 2 1.1 3.3 3.1 4v1.5C7.7 17.5 6 15.1 6 11.5zM13.5 7.5H19v5h-3.1c.1 2 1.1 3.3 3.1 4v1.5c-3.8-.5-5.5-2.9-5.5-6.5z" /></svg>;
  }
  if (name === "pencil") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 16.5-.7 3.2 3.2-.7L18 8.5 15.5 6z" /><path d="m14.5 7 2.5 2.5M5 20h14" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4.5h9.5L18 7v13H6z" /><path d="M15.5 4.5V8H18M8.5 11h7M8.5 14h7M8.5 17h4" /></svg>;
}

type PairFormatter = (value: number | null) => string;

function CoupleMineValues({ value, format }: { value: CoupleMine; format: PairFormatter }) {
  return (
    <div className="review-metric-values">
      <p><span>우리</span><strong>{format(value.couple)}</strong></p>
      <p><span>나</span><strong>{format(value.mine)}</strong></p>
    </div>
  );
}

function ComparisonCard({
  label,
  description,
  icon,
  range,
  baseline,
  format,
  tone,
  weeks,
}: {
  label: string;
  description: string;
  icon: ReviewIconName;
  range: CoupleMine;
  baseline: CoupleMine;
  format: PairFormatter;
  tone: "coral" | "peach" | "lavender";
  weeks: number;
}) {
  return (
    <article className={`review-comparison-card review-comparison-card--${tone}`}>
      <div className="review-comparison-card__heading">
        <span className="review-icon-bubble"><ReviewIcon name={icon} /></span>
        <div><h3>{label}</h3><p>{description}</p></div>
      </div>
      <div className="review-comparison-card__body">
        <div className="review-comparison-card__side review-comparison-card__side--range">
          <span>이번 구간</span>
          <CoupleMineValues value={range} format={format} />
        </div>
        <span className="review-comparison-card__divider" aria-hidden="true">→</span>
        <div className="review-comparison-card__side review-comparison-card__side--baseline">
          <span>평소 · 지난 {weeks.toLocaleString("ko-KR")}주</span>
          <CoupleMineValues value={baseline} format={format} />
        </div>
      </div>
    </article>
  );
}

function CountComparisonCard({ value, baseline, weeks }: { value: number; baseline: number | null; weeks: number }) {
  return (
    <article className="review-comparison-card review-comparison-card--sky">
      <div className="review-comparison-card__heading">
        <span className="review-icon-bubble"><ReviewIcon name="mail" /></span>
        <div><h3>총 메시지 수</h3><p>커플 전체</p></div>
      </div>
      <div className="review-comparison-card__body review-comparison-card__body--count">
        <div className="review-comparison-card__side review-comparison-card__side--range">
          <span>이번 구간</span><strong className="review-count-value">{formatCount(value)}</strong>
        </div>
        <span className="review-comparison-card__divider" aria-hidden="true">→</span>
        <div className="review-comparison-card__side review-comparison-card__side--baseline">
          <span>평소 · 지난 {weeks.toLocaleString("ko-KR")}주</span><strong className="review-count-value">{formatCount(baseline)}</strong>
        </div>
      </div>
    </article>
  );
}

function MetricsComparison({ range, baseline }: { range: RangeMetrics; baseline: BaselineMetrics }) {
  return (
    <div className="review-comparison-grid" role="table" aria-label="선택 구간과 평소 지표 비교">
      <ComparisonCard label="질문 비율" description="대화 중 질문 비율" icon="heart-chat" range={range.question_rate} baseline={baseline.question_rate} format={formatPercent} tone="coral" weeks={baseline.weeks} />
      <ComparisonCard label="답장 시간" description="답장 간격 중앙값" icon="clock" range={range.reply_gap_median_min} baseline={baseline.reply_gap_median_min} format={formatMinutes} tone="peach" weeks={baseline.weeks} />
      <CountComparisonCard value={range.message_count} baseline={baseline.message_count} weeks={baseline.weeks} />
    </div>
  );
}

function NoteList({ notes }: { notes: NoteResponse[] }) {
  if (notes.length === 0) {
    return <div className="review-note-empty"><span className="review-note-empty__icon"><ReviewIcon name="notebook" /></span><p>이 기간에 남긴 메모가 아직 없어요.</p></div>;
  }

  return (
    <div className="review-note-list">
      {notes.map((note) => (
        <article key={note.note_id} className="review-note-item">
          <div className="review-note-item__topline">
            <Badge who={note.author}>{note.author === "a" ? "나" : "상대"}</Badge>
            <time dateTime={note.created_at}>{formatDateTime(note.created_at)}</time>
          </div>
          <p>{note.body}</p>
        </article>
      ))}
    </div>
  );
}

function ReviewSessionCard({
  session,
  onSelect,
}: {
  session: ReviewResponse["sessions"][number];
  onSelect: (session: ReviewResponse["sessions"][number]) => void;
}) {
  const canViewMessages = session.msg_count > 0;

  return (
    <article className="review-session-card">
      <div
        className="review-session-card__details"
      >
        <button
          className="review-session-card__summary"
          type="button"
          disabled={!canViewMessages}
          onClick={() => onSelect(session)}
          aria-label={canViewMessages ? `${formatSessionDate(session.started_at)} 메시지 보기` : undefined}
        >
          <div className="review-session-card__content">
            <div className="review-session-card__date" aria-hidden="true">
              <span>{new Intl.DateTimeFormat("ko-KR", { month: "short", timeZone: "Asia/Seoul" }).format(new Date(session.started_at))}</span>
              <strong>{new Intl.DateTimeFormat("ko-KR", { day: "numeric", timeZone: "Asia/Seoul" }).format(new Date(session.started_at))}</strong>
            </div>
            <div className="review-session-card__intro">
              <p className="review-session-card__eyebrow">CONVERSATION · #{session.session_id}</p>
              <h3>{formatSessionDate(session.started_at)}의 대화</h3>
              <time dateTime={session.started_at}>
                {formatSessionTime(session.started_at)} — {formatSessionTime(session.ended_at)}
              </time>
            </div>
            <div className="review-session-card__facts">
              <span className="review-session-card__fact">
                <ReviewIcon name="mail" />
                <span>메시지</span>
                <strong>{session.msg_count.toLocaleString()}개</strong>
              </span>
              <span className="review-session-card__starter">
                {session.initiated_by_me ? "내가 대화 시작" : "상대가 대화 시작"}
              </span>
            </div>
            <div className={`review-session-card__toggle${canViewMessages ? "" : " review-session-card__toggle--disabled"}`}>
              <span>{canViewMessages ? "메시지 보기" : "메시지 없음"}</span>
              {canViewMessages && <i aria-hidden="true" />}
            </div>
          </div>
        </button>
      </div>
    </article>
  );
}

function ReviewConversationModal({
  session,
  coupleId,
  onClose,
}: {
  session: ReviewResponse["sessions"][number] | null;
  coupleId: string;
  onClose: () => void;
}) {
  const sessionId = session?.session_id;
  const messageQuery = useInfiniteQuery({
    queryKey: ["review-session-messages", coupleId, sessionId],
    enabled: Boolean(coupleId && sessionId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      if (!sessionId) throw new Error("대화 세션을 확인할 수 없습니다.");
      return api.get<ReviewSessionMessagesResponse>(
        `/api/couples/${coupleId}/review/sessions/${sessionId}/messages?offset=${Number(pageParam)}&limit=${MESSAGE_PAGE_SIZE}`,
      );
    },
    getNextPageParam: (lastPage) => lastPage.next_offset ?? undefined,
    staleTime: 30_000,
    retry: 1,
  });
  const messages = messageQuery.data?.pages.flatMap((page) => page.messages) ?? [];
  const total = messageQuery.data?.pages[0]?.total ?? session?.msg_count ?? 0;

  return (
    <Modal
      open={Boolean(session)}
      onClose={onClose}
      title={session ? `${formatSessionDate(session.started_at)}의 대화` : undefined}
      className="review-conversation-modal"
    >
      <section className="review-conversation-modal__body" aria-label="대화 메시지" aria-live="polite">
        <div className="review-session-card__messages-heading">
          <div>
            <p className="review-session-card__messages-eyebrow">OUR CHAT</p>
            <h4>그날 나눈 이야기</h4>
            {session && (
              <time dateTime={session.started_at}>
                {formatSessionTime(session.started_at)} — {formatSessionTime(session.ended_at)}
              </time>
            )}
          </div>
          <span>{messages.length.toLocaleString()} / {total.toLocaleString()}개</span>
        </div>

        {messageQuery.isLoading && (
          <div className="review-session-card__message-state">
            <span className="review-session-card__loading-dot" aria-hidden="true" />
            <p>암호화된 대화를 안전하게 불러오고 있어요.</p>
          </div>
        )}

        {messageQuery.isError && (
          <div className="review-session-card__message-state review-session-card__message-state--error">
            <p>메시지를 불러오지 못했어요.</p>
            <button type="button" onClick={() => messageQuery.refetch()}>다시 불러오기</button>
          </div>
        )}

        {messageQuery.isSuccess && messages.length === 0 && (
          <div className="review-session-card__message-state">
            <p>표시할 메시지가 없어요.</p>
          </div>
        )}

        {messages.length > 0 && (
          <div className="review-session-card__message-list">
            {messages.map((message) => (
              <article
                className={`review-session-card__message review-session-card__message--${message.mine ? "mine" : "partner"}`}
                key={message.message_id}
              >
                <span
                  className="review-session-card__speaker"
                  aria-label={message.mine ? "나" : "연인"}
                >
                  {message.mine ? "나" : <span aria-hidden="true">♥</span>}
                </span>
                <div>
                  <p>{message.text}</p>
                  <time dateTime={message.at}>{formatDateTime(message.at)}</time>
                </div>
              </article>
            ))}
          </div>
        )}

        {messageQuery.hasNextPage && (
          <button
            className="review-session-card__load-more"
            type="button"
            disabled={messageQuery.isFetchingNextPage}
            onClick={() => messageQuery.fetchNextPage()}
          >
            {messageQuery.isFetchingNextPage ? "더 불러오는 중…" : "메시지 30개 더 보기"}
          </button>
        )}
      </section>
    </Modal>
  );
}

export default function Review() {
  const { data: coupleData } = useCoupleMe();
  const coupleId = coupleData?.couple_id;
  const initialRange = getInitialRange();
  const [start, setStart] = useState(initialRange.start);
  const [end, setEnd] = useState(initialRange.end);
  const [noteBody, setNoteBody] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const [visibleSessionCount, setVisibleSessionCount] = useState(SESSION_BATCH_SIZE);
  const [selectedSession, setSelectedSession] = useState<ReviewResponse["sessions"][number] | null>(null);
  const queryClient = useQueryClient();
  const rangeError = getRangeError(start, end);
  const queryKey = ["review", coupleId, start, end];

  useEffect(() => {
    setVisibleSessionCount(SESSION_BATCH_SIZE);
    setSelectedSession(null);
  }, [coupleId, end, start]);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey,
    enabled: Boolean(coupleId) && !rangeError,
    queryFn: () => api.get<ReviewResponse>(
      `/api/couples/${coupleId}/review?start=${encodeURIComponent(toIsoStart(start))}&end=${encodeURIComponent(toIsoEnd(end))}`,
    ),
    staleTime: 30_000,
  });

  const noteMutation = useMutation({
    mutationFn: (payload: NoteCreateRequest) => {
      if (!coupleId) throw new Error("연결된 커플 정보를 확인할 수 없습니다.");
      return api.post<NoteResponse>(`/api/couples/${coupleId}/notes`, payload);
    },
    onSuccess: (note) => {
      queryClient.setQueryData<ReviewResponse>(queryKey, (current) =>
        current ? { ...current, notes: [...current.notes, note] } : current,
      );
      setNoteBody("");
      setNoteError(null);
    },
    onError: (requestError) => setNoteError(getErrorMessage(requestError)),
  });

  const addNote = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = noteBody.trim();
    if (!body) {
      setNoteError("메모 내용을 입력해주세요.");
      return;
    }
    if (body.length > 500) {
      setNoteError("메모는 500자 이내로 작성해주세요.");
      return;
    }

    setNoteError(null);
    noteMutation.mutate({
      range_start: toIsoStart(start),
      range_end: toIsoEnd(end),
      body,
    });
  };

  const recentSessions = data
    ? [...data.sessions].sort((left, right) => Date.parse(right.started_at) - Date.parse(left.started_at))
    : [];
  const visibleSessions = recentSessions.slice(0, visibleSessionCount);

  const loadMoreSessionsOnScroll = (event: UIEvent<HTMLDivElement>) => {
    const list = event.currentTarget;
    const isNearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 120;
    if (!isNearBottom || visibleSessionCount >= recentSessions.length) return;

    setVisibleSessionCount((current) => Math.min(current + SESSION_BATCH_SIZE, recentSessions.length));
  };

  return (
    <main className="review-page">
      <section className="review-range-card" aria-labelledby="review-range-heading">
        <div className="review-range-card__heading">
          <span className="review-section-icon"><ReviewIcon name="calendar" /></span>
          <div><p className="review-section-eyebrow">A SMALL PAUSE</p><h2 id="review-range-heading">돌아볼 기간을 골라주세요</h2></div>
          {isFetching && !isLoading && <span className="review-fetching">조회 중…</span>}
        </div>
        <div className="review-date-fields">
          <CalendarDatePicker
            label="시작일"
            value={start}
            max={end || undefined}
            rangeStart={start}
            rangeEnd={end}
            onChange={setStart}
          />
          <span className="review-date-arrow" aria-hidden="true">→</span>
          <CalendarDatePicker
            label="종료일"
            value={end}
            min={start || undefined}
            rangeStart={start}
            rangeEnd={end}
            onChange={setEnd}
          />
        </div>
        <div className="review-range-summary"><span>선택한 범위</span><strong>{start && end ? formatDateRange(start, end) : "날짜를 선택해주세요"}</strong></div>
        {rangeError && <p role="alert" className="review-form-error">{rangeError}</p>}
      </section>

      {isLoading && !rangeError && (
        <Card className="review-state-card review-loading-card">
          <span className="review-state-icon"><ReviewIcon name="sparkle" /></span>
          <p>선택한 기간의 돌아보기 데이터를 불러오는 중이에요…</p>
          <div className="review-loading-line" />
        </Card>
      )}

      {error && !isLoading && (
        <Card className="review-state-card review-error-card">
          <span className="review-state-icon"><ReviewIcon name="sparkle" /></span>
          <Badge tone="neutral">불러오기 실패</Badge>
          <h2>돌아보기 데이터를 불러오지 못했어요.</h2>
          <p>{getErrorMessage(error)}</p>
          <Button className="mt-4" onClick={() => refetch()}>다시 시도</Button>
        </Card>
      )}

      {data && !error && (
        <>
          <section className="review-section review-metrics-section" aria-labelledby="metrics-heading">
            <div className="review-section-heading">
              <div><span className="review-section-eyebrow">A LITTLE LOOK BACK</span><h2 id="metrics-heading">우리의 대화는 어떻게 달랐을까요?</h2><p>{formatDateRange(data.range.start, data.range.end)}</p></div>
              <Badge tone="neutral">평소와 비교</Badge>
            </div>
            <MetricsComparison range={data.metrics.range} baseline={data.metrics.baseline} />
          </section>

          <section className="review-insight-card" aria-label="이번 구간의 작은 변화">
            <span className="review-insight-card__sparkle"><ReviewIcon name="sparkle" /></span>
            <div><p className="review-section-eyebrow">이번 구간의 작은 변화 ✨</p><p className="review-insight-card__comment">{data.metrics.comment}</p></div>
            <span className="review-insight-card__quote"><ReviewIcon name="quote" /></span>
          </section>

          {data.sessions.length === 0 && (
            <Card className="review-empty-card">
              <span className="review-empty-card__icon"><ReviewIcon name="heart-chat" /></span>
              <Badge tone="neutral">대화 없음</Badge>
              <p>선택한 기간에 확인된 대화 세션이 없어요. 다른 기간을 선택해보세요.</p>
            </Card>
          )}

          {data.sessions.length > 0 && (
            <section className="review-section review-sessions-section" aria-labelledby="sessions-heading">
              <div className="review-section-heading"><div><span className="review-section-eyebrow">OUR CONVERSATIONS</span><h2 id="sessions-heading">우리의 대화 기록</h2></div><span className="review-section-count">{data.sessions.length}개</span></div>
              <div className="review-session-scroll-shell">
                <div
                  className={`review-session-list${recentSessions.length > 3 ? " review-session-list--scrollable" : ""}`}
                  onScroll={loadMoreSessionsOnScroll}
                  tabIndex={recentSessions.length > 3 ? 0 : undefined}
                  aria-label={recentSessions.length > 3
                    ? "최근 대화 기록. 목록 안에서 스크롤하면 이전 대화를 볼 수 있습니다."
                    : "최근 대화 기록"
                  }
                >
                  {visibleSessions.map((session) => (
                    <ReviewSessionCard key={session.session_id} session={session} onSelect={setSelectedSession} />
                  ))}
                </div>
                {recentSessions.length > 3 && (
                  <span className="review-session-scroll-hint" aria-hidden="true">스크롤해서 이전 대화 보기 ↓</span>
                )}
              </div>
            </section>
          )}

          <section className="review-notes-layout" aria-label="메모">
            <Card className="review-notes-card">
              <div className="review-card-heading"><div><span className="review-section-eyebrow">MEMORIES TO KEEP</span><h2>이 기간에 남긴 메모</h2><p>선택한 기간에 대한 생각을 남겨보세요.</p></div><Badge tone="neutral">{data.notes.length}개</Badge></div>
              <NoteList notes={data.notes} />
            </Card>

            <Card className="review-note-form-card">
              <div className="review-card-heading"><div><span className="review-section-eyebrow">A NOTE FOR US</span><h2>이 기간에 남기고 싶은 메모</h2><p>이 메모는 {formatDateRange(data.range.start, data.range.end)}에 연결돼요.</p></div><span className="review-pencil-icon"><ReviewIcon name="pencil" /></span></div>
              <form className="review-note-form" onSubmit={addNote}>
                <textarea value={noteBody} onChange={(event) => setNoteBody(event.target.value)} maxLength={500} rows={5} placeholder="예: 이 기간에는 서로 바빠서 짧게 대화했어요." aria-label="메모 내용" />
                <div className="review-note-form__footer"><span>{noteBody.length}/500</span><Button type="submit" disabled={noteMutation.isPending}>{noteMutation.isPending ? "저장 중…" : "메모 저장"}</Button></div>
                {noteError && <p role="alert" className="review-form-error">{noteError}</p>}
              </form>
            </Card>
          </section>

          <ReviewConversationModal
            session={selectedSession}
            coupleId={coupleId ?? ""}
            onClose={() => setSelectedSession(null)}
          />
        </>
      )}
    </main>
  );
}
