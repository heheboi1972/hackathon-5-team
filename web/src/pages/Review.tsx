// 역할: 돌아보기 — 구간 선택 → 지표 vs 기준선 → 메모 (참조: FR-005, API_SPEC §5)
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiClientError, api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import type { NoteCreateRequest, NoteResponse, ReviewResponse } from "../api/types";

const COUPLE_ID = "00000000-0000-0000-0000-000000000001";
const REVIEW_BASE_PATH = `/api/couples/${COUPLE_ID}/review`;
const NOTES_PATH = `/api/couples/${COUPLE_ID}/notes`;

type MetricValue = {
  couple?: unknown;
  mine?: unknown;
};

type MetricGroup = Record<string, unknown>;

type MetricConfig = {
  key: string;
  label: string;
  description: string;
  unit: "percent" | "chars" | "minutes" | "messages";
  people: boolean;
};

const METRICS: MetricConfig[] = [
  {
    key: "question_rate",
    label: "질문 비율",
    description: "대화 중 질문이 차지한 비율",
    unit: "percent",
    people: true,
  },
  {
    key: "message_length_median",
    label: "메시지 길이",
    description: "메시지 하나의 중간 길이",
    unit: "chars",
    people: true,
  },
  {
    key: "reply_gap_median_min",
    label: "답장 시간",
    description: "메시지 사이 중간 답장 간격",
    unit: "minutes",
    people: true,
  },
  {
    key: "session_length_median",
    label: "세션 길이",
    description: "세션 하나의 중간 메시지 수",
    unit: "messages",
    people: false,
  },
];

function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getInitialRange(): { start: string; end: string } {
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

function getMetricValue(group: MetricGroup | undefined, key: string): MetricValue | number | null {
  const value = group?.[key];
  if (typeof value === "number" || value === null) return value;
  if (typeof value === "object" && value !== null) return value as MetricValue;
  return null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatMetric(value: unknown, unit: MetricConfig["unit"]): string {
  const number = numberValue(value);
  if (number === null) return "-";
  const formatted = number.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  if (unit === "percent") return `${(number * 100).toFixed(1)}%`;
  if (unit === "chars") return `${formatted}자`;
  if (unit === "minutes") return `${formatted}분`;
  return `${formatted}개`;
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

function MetricCard({ config, range, baseline }: {
  config: MetricConfig;
  range: MetricGroup;
  baseline: MetricGroup;
}) {
  const rangeValue = getMetricValue(range, config.key);
  const baselineValue = getMetricValue(baseline, config.key);
  const rangePair = typeof rangeValue === "object" && rangeValue !== null ? rangeValue : null;
  const baselinePair = typeof baselineValue === "object" && baselineValue !== null ? baselineValue : null;

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900">{config.label}</h3>
          <p className="mt-1 text-xs text-gray-500">{config.description}</p>
        </div>
        <Badge tone="neutral">선택 기간 vs 기준선</Badge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {config.people ? (
          <>
            <MetricValue label="우리" value={rangePair?.couple} baseline={baselinePair?.couple} unit={config.unit} />
            <MetricValue label="나" value={rangePair?.mine} baseline={baselinePair?.mine} unit={config.unit} />
          </>
        ) : (
          <MetricValue
            label="전체"
            value={rangeValue}
            baseline={baselineValue}
            unit={config.unit}
          />
        )}
      </div>
    </Card>
  );
}

function MetricValue({ label, value, baseline, unit }: {
  label: string;
  value: unknown;
  baseline: unknown;
  unit: MetricConfig["unit"];
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-bold text-gray-900">{formatMetric(value, unit)}</p>
      <p className="mt-1 text-xs text-gray-500">기준선 {formatMetric(baseline, unit)}</p>
    </div>
  );
}

function NoteList({ notes }: { notes: NoteResponse[] }) {
  if (notes.length === 0) {
    return <p className="text-sm text-gray-500">이 기간에 남긴 메모가 아직 없어요.</p>;
  }

  return (
    <div className="space-y-3">
      {notes.map((note) => (
        <article key={note.note_id} className="rounded-lg border border-rose-100 bg-rose-50/50 p-3">
          <div className="flex items-center justify-between gap-2">
            <Badge who={note.author}>{note.author === "a" ? "나" : "상대"}</Badge>
            <time className="text-xs text-gray-500" dateTime={note.created_at}>
              {formatDateTime(note.created_at)}
            </time>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm text-gray-800">{note.body}</p>
        </article>
      ))}
    </div>
  );
}

export default function Review() {
  const initialRange = getInitialRange();
  const [start, setStart] = useState(initialRange.start);
  const [end, setEnd] = useState(initialRange.end);
  const [noteBody, setNoteBody] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const rangeError = getRangeError(start, end);
  const queryKey = ["review", start, end];

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey,
    enabled: !rangeError,
    queryFn: () => api.get<ReviewResponse>(
      `${REVIEW_BASE_PATH}?start=${encodeURIComponent(toIsoStart(start))}&end=${encodeURIComponent(toIsoEnd(end))}`,
    ),
    staleTime: 30_000,
  });

  const noteMutation = useMutation({
    mutationFn: (payload: NoteCreateRequest) => api.post<NoteResponse>(NOTES_PATH, payload),
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

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6 sm:p-8">
      <header className="space-y-2">
        <p className="text-sm font-medium text-rose-600">선택한 대화 돌아보기</p>
        <h1 className="text-2xl font-bold text-gray-900">이 구간을 돌아봐요</h1>
        <p className="text-gray-600">선택한 기간의 지표를 평소 기준선과 함께 살펴보고, 기억하고 싶은 장면을 메모해보세요.</p>
      </header>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[9rem] flex-1 space-y-1 text-sm font-medium text-gray-700">
            시작일
            <input
              type="date"
              value={start}
              max={end || undefined}
              onChange={(event) => setStart(event.target.value)}
              className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
            />
          </label>
          <span className="pb-2 text-gray-400">부터</span>
          <label className="min-w-[9rem] flex-1 space-y-1 text-sm font-medium text-gray-700">
            종료일
            <input
              type="date"
              value={end}
              min={start || undefined}
              onChange={(event) => setEnd(event.target.value)}
              className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
            />
          </label>
          {isFetching && !isLoading && <span className="pb-2 text-xs text-gray-500">조회 중…</span>}
        </div>
        {rangeError && <p role="alert" className="mt-3 text-sm text-red-700">{rangeError}</p>}
      </Card>

      {isLoading && !rangeError && (
        <Card>
          <p className="text-gray-600">선택한 기간의 돌아보기 데이터를 불러오는 중이에요…</p>
          <div className="mt-4 h-2 animate-pulse rounded bg-gray-200" />
        </Card>
      )}

      {error && !isLoading && (
        <Card className="border-red-200 bg-red-50">
          <Badge tone="neutral">불러오기 실패</Badge>
          <h2 className="mt-2 font-semibold text-gray-900">돌아보기 데이터를 불러오지 못했어요.</h2>
          <p className="mt-1 text-sm text-red-700">{getErrorMessage(error)}</p>
          <Button className="mt-4" onClick={() => refetch()}>다시 시도</Button>
        </Card>
      )}

      {data && !error && (
        <>
          <section className="space-y-3" aria-labelledby="metrics-heading">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <h2 id="metrics-heading" className="text-lg font-semibold text-gray-900">지표와 기준선</h2>
                <p className="mt-1 text-sm text-gray-600">{formatDateRange(data.range.start, data.range.end)}</p>
              </div>
              <Badge tone="neutral">
                기준선 · 최근 {numberValue((data.metrics.baseline as MetricGroup).weeks) ?? "-"}주 평균
              </Badge>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {METRICS.map((config) => (
                <MetricCard
                  key={config.key}
                  config={config}
                  range={data.metrics.range as MetricGroup}
                  baseline={data.metrics.baseline as MetricGroup}
                />
              ))}
            </div>
          </section>

          {data.sessions.length === 0 && (
            <Card className="border-amber-200 bg-amber-50">
              <Badge tone="neutral">대화 없음</Badge>
              <p className="mt-2 text-sm text-amber-800">선택한 기간에 확인된 대화 세션이 없어요. 다른 기간을 선택해보세요.</p>
            </Card>
          )}

          {data.sessions.length > 0 && (
            <section className="space-y-3" aria-labelledby="sessions-heading">
              <div className="flex items-baseline justify-between gap-2">
                <h2 id="sessions-heading" className="text-lg font-semibold text-gray-900">대화 세션</h2>
                <span className="text-sm text-gray-500">{data.sessions.length}개</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {data.sessions.map((session) => (
                  <Card key={session.session_id}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-gray-900">세션 #{session.session_id}</p>
                        <p className="mt-1 text-sm text-gray-600">
                          {formatDateTime(session.started_at)} ~ {formatDateTime(session.ended_at)}
                        </p>
                      </div>
                      <Badge who={session.initiator}>{session.initiator === "a" ? "나부터" : "상대부터"}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-gray-600">메시지 {session.msg_count.toLocaleString()}개</p>
                  </Card>
                ))}
              </div>
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" aria-label="메모">
            <Card>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">이 기간의 메모</h2>
                  <p className="mt-1 text-sm text-gray-600">선택한 기간에 대한 생각을 남겨보세요.</p>
                </div>
                <Badge tone="neutral">{data.notes.length}개</Badge>
              </div>
              <div className="mt-4">
                <NoteList notes={data.notes} />
              </div>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold text-gray-900">새 메모 작성</h2>
              <p className="mt-1 text-sm text-gray-600">이 메모는 {formatDateRange(data.range.start, data.range.end)}에 연결돼요.</p>
              <form className="mt-4 space-y-3" onSubmit={addNote}>
                <textarea
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  maxLength={500}
                  rows={5}
                  placeholder="예: 이 기간에는 서로 바빠서 짧게 대화했어요."
                  className="w-full resize-y rounded border px-3 py-2 text-sm outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
                  aria-label="메모 내용"
                />
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-gray-500">{noteBody.length}/500</span>
                  <Button type="submit" disabled={noteMutation.isPending}>
                    {noteMutation.isPending ? "저장 중…" : "메모 저장"}
                  </Button>
                </div>
                {noteError && <p role="alert" className="text-sm text-red-700">{noteError}</p>}
              </form>
            </Card>
          </section>
        </>
      )}
    </main>
  );
}
