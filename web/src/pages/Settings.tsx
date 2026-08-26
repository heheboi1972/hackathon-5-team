import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import Modal from "../components/Modal";
import type { CoupleMeResponse, CoupleSettingsUpdate, Who } from "../api/types";

const COUPLE_ME_PATH = "/api/couples/me";
const COUPLE_ME_QUERY_KEY = ["couple-me"];

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return value.slice(0, 10);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "요청을 처리하지 못했어요.";
}

function memberLabel(who: Who, me: Who | null | undefined): string {
  return who === me ? "나" : "상대방";
}

function LoadingState() {
  return (
    <main className="settings-page settings-page--state">
      <Card className="settings-card settings-card--pink">
        <div className="settings-skeleton__title h-5 w-32 animate-pulse rounded bg-gray-200" />
        <div className="settings-skeleton__body mt-4 h-16 animate-pulse rounded bg-gray-100" />
      </Card>
    </main>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="settings-page settings-page--state">
      <Card className="settings-card settings-card--danger border-red-200 bg-red-50">
        <div className="settings-card__heading">
          <span className="settings-icon settings-icon--danger" aria-hidden="true">!</span>
          <div>
            <Badge tone="neutral">불러오기 실패</Badge>
            <h2>설정 정보를 불러오지 못했어요.</h2>
          </div>
        </div>
        <p className="settings-card__description text-red-700">잠시 후 다시 시도해 주세요.</p>
        <Button className="mt-4" onClick={onRetry}>
          다시 시도
        </Button>
      </Card>
    </main>
  );
}

function EmptyState() {
  return (
    <main className="settings-page settings-page--state">
      <Card className="settings-card settings-card--lavender text-center">
        <span className="settings-state-icon" aria-hidden="true">♡</span>
        <Badge tone="neutral">커플 연결 필요</Badge>
        <h2 className="mt-3 text-lg font-semibold text-gray-900">
          커플을 연결하면 대화 리포트를 시작할 수 있어요.
        </h2>
        <p className="settings-card__description">현재 연결된 커플이 없어요.</p>
        <Link
          to="/onboarding"
          className="settings-link-button mt-5 inline-flex rounded bg-rose-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-300"
        >
          커플 연결하기
        </Link>
      </Card>
    </main>
  );
}

function DeletedState() {
  return (
    <main className="settings-page settings-page--state">
      <Card className="settings-card settings-card--pink border-rose-200 bg-rose-50">
        <div className="settings-card__heading">
          <span className="settings-icon settings-icon--pink" aria-hidden="true">♡</span>
          <Badge tone="neutral">연결 해제 완료</Badge>
        </div>
        <h2 className="mt-3 text-lg font-semibold text-gray-900">
          커플 연결을 해제했어요.
        </h2>
        <p className="settings-card__description mt-2 text-sm leading-6 text-gray-700">
          커플의 대화, 지표, 리포트, 메모가 삭제되었습니다. 다시 사용하려면 새로운 커플 연결을 시작해 주세요.
        </p>
        <Link
          to="/onboarding"
          className="settings-link-button mt-5 inline-flex rounded bg-rose-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-300"
        >
          커플 연결 시작하기
        </Link>
      </Card>
    </main>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [firstMetAt, setFirstMetAt] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: COUPLE_ME_QUERY_KEY,
    queryFn: () => api.get<CoupleMeResponse>(COUPLE_ME_PATH),
    staleTime: 30_000,
  });

  useEffect(() => {
    setFirstMetAt(data?.first_met_at ?? "");
  }, [data?.first_met_at]);

  const deleteCouple = useMutation({
    mutationFn: async () => {
      if (!data?.couple_id) throw new Error("해제할 커플 연결이 없어요.");
      return api.delete(`/api/couples/${data.couple_id}`);
    },
    onSuccess: () => {
      setConfirmOpen(false);
      setDeleted(true);
      queryClient.setQueryData<CoupleMeResponse>(COUPLE_ME_QUERY_KEY, {
        couple_id: null,
        status: null,
      });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
    },
  });

  const updateFirstMetAt = useMutation({
    mutationFn: (payload: CoupleSettingsUpdate) =>
      api.patch<CoupleMeResponse>(COUPLE_ME_PATH, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData<CoupleMeResponse>(COUPLE_ME_QUERY_KEY, updated);
    },
  });

  if (isLoading) return <LoadingState />;
  if (deleted) return <DeletedState />;
  if (error) return <ErrorState onRetry={() => void refetch()} />;
  if (!data || !data.couple_id) return <EmptyState />;

  const members = data.members
    ? (Object.entries(data.members) as [Who, (typeof data.members)[Who]][])
    : [];
  const currentMember = data.me && data.members ? data.members[data.me] : null;
  const jobPercent = data.active_job && data.active_job.total > 0
    ? Math.round((data.active_job.done / data.active_job.total) * 100)
    : 0;

  return (
    <main className="settings-page">
      <section className="grid gap-4 md:grid-cols-2" aria-label="계정 및 커플 정보">
        <Card className="settings-card settings-card--pink">
          <div className="settings-card__heading">
            <span className="settings-icon settings-icon--pink" aria-hidden="true">♡</span>
            <div>
              <p className="settings-card__kicker">내 계정</p>
              <h2 className="mt-1 text-lg font-semibold text-gray-900">
                {currentMember?.display_name ?? "이름 정보 없음"}
              </h2>
            </div>
            {data.me && <Badge className="settings-card__badge" who={data.me}>나</Badge>}
          </div>
          <p className="settings-card__description">우리 공간에 연결된 내 정보를 확인해요.</p>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4 border-t pt-3">
              <dt className="text-gray-500">연결 시작일</dt>
              <dd className="font-medium text-gray-900">{formatDate(data.started_at)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-gray-500">커플 ID</dt>
              <dd className="max-w-[12rem] truncate font-mono text-xs text-gray-600" title={data.couple_id}>
                {data.couple_id}
              </dd>
            </div>
          </dl>
        </Card>

        <Card className="settings-card settings-card--lavender">
          <div className="settings-card__heading">
            <span className="settings-icon settings-icon--lavender" aria-hidden="true">♧</span>
            <div>
              <p className="settings-card__kicker">연결된 상대</p>
              <p className="settings-card__description">함께하는 사람의 연결 정보를 살펴봐요.</p>
            </div>
          </div>
          {members.length > 0 ? (
            <div className="mt-3 space-y-3">
              {members.map(([who, member]) => (
                <div key={member.user_id} className="flex items-center justify-between gap-3 border-b pb-3 last:border-b-0 last:pb-0">
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge who={who}>{memberLabel(who, data.me)}</Badge>
                    <span className="truncate font-medium text-gray-900">{member.display_name}</span>
                  </div>
                  {data.kakao_names?.[who] && (
                    <span className="max-w-[9rem] truncate text-xs text-gray-500" title={data.kakao_names[who]}>
                      카톡: {data.kakao_names[who]}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-gray-600">아직 상대방 정보가 준비되지 않았어요.</p>
          )}
        </Card>
      </section>

      <Card className="settings-card settings-card--pink">
        <div className="settings-card__heading">
          <span className="settings-icon settings-icon--pink" aria-hidden="true">♡</span>
          <div>
            <p className="settings-card__kicker">우리의 기록</p>
            <h2 className="mt-1 text-lg font-semibold text-gray-900">처음 만난 날</h2>
          </div>
        </div>
        <p className="settings-card__description">우리의 시작을 기억해둘 수 있어요.</p>
        <form
          className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"
          onSubmit={(event) => {
            event.preventDefault();
            updateFirstMetAt.mutate({ first_met_at: firstMetAt || null });
          }}
        >
          <label className="flex min-w-0 flex-1 flex-col gap-2 text-sm font-medium text-gray-700" htmlFor="first-met-at">
            처음 만난 날
            <input
              id="first-met-at"
              type="date"
              value={firstMetAt}
              onChange={(event) => setFirstMetAt(event.target.value)}
              className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink shadow-sm outline-none transition focus:border-coral-400 focus:ring-2 focus:ring-coral-200"
            />
          </label>
          <Button type="submit" disabled={updateFirstMetAt.isPending}>
            {updateFirstMetAt.isPending ? "저장 중..." : "저장"}
          </Button>
        </form>
        {!firstMetAt && <p className="mt-2 text-xs text-gray-500">아직 날짜를 설정하지 않았어요.</p>}
        {updateFirstMetAt.error && (
          <p role="alert" className="settings-inline-error mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {errorMessage(updateFirstMetAt.error)}
          </p>
        )}
      </Card>

      {data.data && (
        <Card className="settings-card settings-card--peach">
          <div className="settings-card__heading">
            <span className="settings-icon settings-icon--peach" aria-hidden="true">✦</span>
            <div>
              <p className="settings-card__kicker">대화 데이터</p>
              <h2 className="mt-1 text-lg font-semibold text-gray-900">현재 분석 범위</h2>
            </div>
            <Badge className="settings-card__badge" tone="neutral">{data.data.weeks_available}주</Badge>
          </div>
          <p className="settings-card__description">우리의 대화가 기록된 범위를 한눈에 확인해요.</p>
          <dl className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-gray-500">첫 주</dt>
              <dd className="mt-1 font-medium text-gray-900">{formatDate(data.data.first_week)}</dd>
            </div>
            <div>
              <dt className="text-gray-500">최근 주</dt>
              <dd className="mt-1 font-medium text-gray-900">{formatDate(data.data.last_week)}</dd>
            </div>
            <div>
              <dt className="text-gray-500">분석 주차</dt>
              <dd className="mt-1 font-medium text-gray-900">{data.data.weeks_available}주</dd>
            </div>
            <div>
              <dt className="text-gray-500">메시지</dt>
              <dd className="mt-1 font-medium text-gray-900">{data.data.message_count.toLocaleString()}개</dd>
            </div>
          </dl>
        </Card>
      )}

      {data.active_job && (
        <Card className="settings-card settings-card--peach border-amber-200 bg-amber-50">
          <div className="settings-card__heading">
            <span className="settings-icon settings-icon--peach" aria-hidden="true">✦</span>
            <div>
              <p className="settings-card__kicker text-amber-800">백그라운드 작업 진행 중</p>
              <h2 className="mt-1 font-semibold text-gray-900">리포트를 준비하고 있어요.</h2>
            </div>
            <span className="settings-card__badge text-sm font-medium text-amber-800">{jobPercent}%</span>
          </div>
          <p className="settings-card__description text-amber-800">잠시만 기다려주시면 곧 확인할 수 있어요.</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-amber-100" aria-label="작업 진행률">
            <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${jobPercent}%` }} />
          </div>
          <p className="mt-2 text-sm text-amber-800">
            {data.active_job.done}/{data.active_job.total}개 작업 완료
          </p>
        </Card>
      )}

      <Card className="settings-card settings-card--danger border-red-200">
        <div className="settings-card__heading">
          <span className="settings-icon settings-icon--danger" aria-hidden="true">!</span>
          <div>
            <p className="settings-card__kicker text-red-600">주의가 필요한 작업</p>
            <h2 className="mt-1 text-lg font-semibold text-gray-900">커플 연결 해제</h2>
          </div>
        </div>
        <div>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            연결을 해제하면 커플의 대화, 세션, 지표, 리포트, 메모가 즉시 삭제됩니다. 이 작업은 되돌릴 수 없어요.
          </p>
        </div>
        <Button
          className="mt-4"
          variant="danger"
          onClick={() => setConfirmOpen(true)}
          disabled={deleteCouple.isPending}
        >
          커플 연결 해제
        </Button>
      </Card>

      {deleteCouple.error && (
        <p role="alert" className="settings-inline-error rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorMessage(deleteCouple.error)}
        </p>
      )}

      <Modal
        open={confirmOpen}
        onClose={() => !deleteCouple.isPending && setConfirmOpen(false)}
        title="커플 연결을 해제할까요?"
      >
        <div className="settings-modal-content space-y-4">
          <p className="text-sm leading-6 text-gray-700">
            대화, 지표, 리포트, 메모를 포함한 커플 데이터가 모두 삭제됩니다. 삭제 후에는 복구할 수 없어요.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setConfirmOpen(false)}
              disabled={deleteCouple.isPending}
            >
              취소
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteCouple.mutate()}
              disabled={deleteCouple.isPending}
            >
              {deleteCouple.isPending ? "해제 중..." : "삭제하고 해제"}
            </Button>
          </div>
        </div>
      </Modal>
    </main>
  );
}
