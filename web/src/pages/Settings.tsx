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

function SettingsBackgroundDecor() {
  return (
    <div className="settings-background-decor" aria-hidden="true">
      <span className="settings-decor-heart settings-decor-heart--one">♡</span>
      <span className="settings-decor-heart settings-decor-heart--two">♡</span>
      <span className="settings-decor-sparkle settings-decor-sparkle--one">✦</span>
      <span className="settings-decor-sparkle settings-decor-sparkle--two">✦</span>
      <span className="settings-decor-dot settings-decor-dot--one" />
      <span className="settings-decor-dot settings-decor-dot--two" />
      <span className="settings-decor-dot settings-decor-dot--three" />
    </div>
  );
}

function SettingsIllustration() {
  return (
    <div className="settings-hero-art" aria-hidden="true">
      <span className="settings-hero-art__heart settings-hero-art__heart--one">♡</span>
      <span className="settings-hero-art__heart settings-hero-art__heart--two">♡</span>
      <span className="settings-hero-art__sparkle settings-hero-art__sparkle--one">✦</span>
      <span className="settings-hero-art__sparkle settings-hero-art__sparkle--two">✦</span>
      <svg className="settings-hero-art__svg" viewBox="0 0 360 230" fill="none" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="188" cy="205" rx="132" ry="18" fill="#EADCF7" fillOpacity=".62" />
        <rect x="82" y="54" width="180" height="126" rx="24" fill="#FFFDFD" stroke="#F5B8CB" strokeWidth="3" />
        <rect x="101" y="75" width="142" height="79" rx="15" fill="url(#settings-card-gradient)" />
        <circle cx="139" cy="110" r="19" fill="#FFE2EB" />
        <path d="M130 111.5C130 106.8 133.8 103 138.5 103C143.2 103 147 106.8 147 111.5C147 116.2 143.2 120 138.5 120C133.8 120 130 116.2 130 111.5Z" fill="#FF8CAC" />
        <path d="M124 140C126.6 131.7 132 127.5 138.5 127.5C145 127.5 150.4 131.7 153 140" stroke="#FF8CAC" strokeWidth="4" strokeLinecap="round" />
        <rect x="169" y="98" width="52" height="8" rx="4" fill="#D6C1F3" />
        <rect x="169" y="114" width="39" height="7" rx="3.5" fill="#F7C7B1" />
        <rect x="169" y="129" width="47" height="7" rx="3.5" fill="#F8D9E3" />
        <circle cx="273" cy="139" r="28" fill="#F0E5FF" stroke="#C9ADEB" strokeWidth="3" />
        <path d="M273 121V127M273 151V157M255 139H261M285 139H291M260.3 126.3L264.5 130.5M281.5 147.5L285.7 151.7M285.7 126.3L281.5 130.5M264.5 147.5L260.3 151.7" stroke="#A98AD7" strokeWidth="3" strokeLinecap="round" />
        <circle cx="273" cy="139" r="11" fill="#FFFDFD" stroke="#A98AD7" strokeWidth="3" />
        <path d="M273 133V139L277 142" stroke="#A98AD7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M76 49C76 42.4 81.4 37 88 37C94.6 37 100 42.4 100 49C100 55.6 94.6 61 88 61C81.4 61 76 55.6 76 49Z" fill="#FFC9AD" fillOpacity=".72" />
        <path d="M88 43V55M82 49H94" stroke="#D88D6E" strokeWidth="2.5" strokeLinecap="round" />
        <defs>
          <linearGradient id="settings-card-gradient" x1="101" y1="75" x2="243" y2="154" gradientUnits="userSpaceOnUse">
            <stop stopColor="#FFF0F4" />
            <stop offset="1" stopColor="#F2EBFF" />
          </linearGradient>
        </defs>
      </svg>
      <div className="settings-hero-art__note">
        <span>우리의 작은 약속</span>
        <strong>천천히, 다정하게</strong>
      </div>
    </div>
  );
}

function SettingsHero({ status }: { status?: string }) {
  return (
    <header className="settings-hero">
      <div className="settings-hero__copy">
        <span className="settings-eyebrow">OUR LITTLE SPACE</span>
        <div className="settings-hero__title-row">
          <h1>
            우리의 공간을
            <br />
            편안하게 설정해요 <span aria-hidden="true">♡</span>
          </h1>
          {status && <Badge tone="neutral">{status}</Badge>}
        </div>
        <p>우리에게 맞는 설정을 천천히 정리해보세요.</p>
      </div>
      <SettingsIllustration />
    </header>
  );
}

function LoadingState() {
  return (
    <main className="settings-page settings-page--state">
      <SettingsBackgroundDecor />
      <SettingsHero />
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
      <SettingsBackgroundDecor />
      <SettingsHero />
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
      <SettingsBackgroundDecor />
      <SettingsHero />
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
      <SettingsBackgroundDecor />
      <SettingsHero />
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
    <main className="settings-page">
      <SettingsBackgroundDecor />
      <SettingsHero status={statusLabel(data.status)} />

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
