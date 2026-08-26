import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import Modal from "../components/Modal";
import type { CoupleMeResponse, CoupleStatus, Who } from "../api/types";

const COUPLE_ME_PATH = "/api/couples/me";
const COUPLE_ME_QUERY_KEY = ["couple-me"];

function statusLabel(status: CoupleStatus | null | undefined): string {
  if (status === "active") return "연결됨";
  if (status === "awaiting_confirm") return "수락 대기 중";
  if (status === "pending") return "초대 대기 중";
  if (status === "dissolved") return "해제됨";
  return "연결 정보 없음";
}

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
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <header className="space-y-2">
        <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
        <div className="h-8 w-32 animate-pulse rounded bg-gray-200" />
        <div className="h-4 max-w-md animate-pulse rounded bg-gray-200" />
      </header>
      <Card>
        <div className="h-5 w-32 animate-pulse rounded bg-gray-200" />
        <div className="mt-4 h-16 animate-pulse rounded bg-gray-100" />
      </Card>
    </main>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <header>
        <p className="text-sm font-medium text-rose-600">커플 대화 리포트</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900">설정</h1>
      </header>
      <Card className="border-red-200 bg-red-50">
        <Badge tone="neutral">불러오기 실패</Badge>
        <h2 className="mt-3 text-lg font-semibold text-gray-900">
          설정 정보를 불러오지 못했어요.
        </h2>
        <p className="mt-1 text-sm text-red-700">
          잠시 후 다시 시도해 주세요.
        </p>
        <Button className="mt-4" onClick={onRetry}>
          다시 시도
        </Button>
      </Card>
    </main>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <header className="space-y-2">
        <p className="text-sm font-medium text-rose-600">커플 대화 리포트</p>
        <h1 className="text-2xl font-bold text-gray-900">설정</h1>
        <p className="text-gray-600">현재 연결된 커플이 없어요.</p>
      </header>
      <Card className="text-center">
        <Badge tone="neutral">커플 연결 필요</Badge>
        <h2 className="mt-3 text-lg font-semibold text-gray-900">
          커플을 연결하면 대화 리포트를 시작할 수 있어요.
        </h2>
        <Link
          to="/onboarding"
          className="mt-5 inline-flex rounded bg-rose-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-300"
        >
          커플 연결하기
        </Link>
      </Card>
    </main>
  );
}

function DeletedState() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <header className="space-y-2">
        <p className="text-sm font-medium text-rose-600">커플 대화 리포트</p>
        <h1 className="text-2xl font-bold text-gray-900">설정</h1>
      </header>
      <Card className="border-rose-200 bg-rose-50">
        <Badge tone="neutral">연결 해제 완료</Badge>
        <h2 className="mt-3 text-lg font-semibold text-gray-900">
          커플 연결을 해제했어요.
        </h2>
        <p className="mt-2 text-sm leading-6 text-gray-700">
          커플의 대화, 지표, 리포트, 메모가 삭제되었습니다. 다시 사용하려면 새로운 커플 연결을 시작해 주세요.
        </p>
        <Link
          to="/onboarding"
          className="mt-5 inline-flex rounded bg-rose-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-300"
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

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: COUPLE_ME_QUERY_KEY,
    queryFn: () => api.get<CoupleMeResponse>(COUPLE_ME_PATH),
    staleTime: 30_000,
  });

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
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
      <header className="space-y-2">
        <p className="text-sm font-medium text-rose-600">커플 대화 리포트</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">설정</h1>
          <Badge tone="neutral">{statusLabel(data.status)}</Badge>
        </div>
        <p className="text-gray-600">연결된 커플과 계정 정보를 확인할 수 있어요.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-2" aria-label="계정 및 커플 정보">
        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-gray-500">내 계정</p>
              <h2 className="mt-1 text-lg font-semibold text-gray-900">
                {currentMember?.display_name ?? "이름 정보 없음"}
              </h2>
            </div>
            {data.me && <Badge who={data.me}>나</Badge>}
          </div>
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

        <Card>
          <p className="text-sm font-medium text-gray-500">연결된 상대</p>
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

      {data.data && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-gray-500">대화 데이터</p>
              <h2 className="mt-1 text-lg font-semibold text-gray-900">현재 분석 범위</h2>
            </div>
            <Badge tone="neutral">{data.data.weeks_available}주</Badge>
          </div>
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
        <Card className="border-amber-200 bg-amber-50">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-amber-800">백그라운드 작업 진행 중</p>
              <h2 className="mt-1 font-semibold text-gray-900">리포트를 준비하고 있어요.</h2>
            </div>
            <span className="text-sm font-medium text-amber-800">{jobPercent}%</span>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-amber-100" aria-label="작업 진행률">
            <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${jobPercent}%` }} />
          </div>
          <p className="mt-2 text-sm text-amber-800">
            {data.active_job.done}/{data.active_job.total}개 작업 완료
          </p>
        </Card>
      )}

      <Card className="border-red-200">
        <div>
          <p className="text-sm font-medium text-red-600">주의가 필요한 작업</p>
          <h2 className="mt-1 text-lg font-semibold text-gray-900">커플 연결 해제</h2>
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
        <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorMessage(deleteCouple.error)}
        </p>
      )}

      <Modal
        open={confirmOpen}
        onClose={() => !deleteCouple.isPending && setConfirmOpen(false)}
        title="커플 연결을 해제할까요?"
      >
        <div className="space-y-4">
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
