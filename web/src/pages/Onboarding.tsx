// 역할: 온보딩 — 가입 → 초대코드 → 수락대기 → 수락 (참조: FR-001, TRD §6.1) — 시여 담당
// 스캐폴딩: 화면 뼈대만. 실제 API 연결·react-hook-form+zod 폼은 TODO(시여)
import { useState } from "react";
import { api } from "../api/client";
import type { InviteResponse, JoinResponse } from "../api/types";

export default function Onboarding() {
  const [invite, setInvite] = useState<InviteResponse | null>(null);
  const [code, setCode] = useState("");
  const [joined, setJoined] = useState<JoinResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createInvite = async () => {
    try {
      setInvite(await api.post<InviteResponse>("/api/couples/invite"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const join = async () => {
    try {
      setJoined(await api.post<JoinResponse>("/api/couples/join", { invite_code: code }));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <main className="mx-auto max-w-md space-y-6 p-8">
      <h1 className="text-2xl font-bold">커플 대화 리포트</h1>
      <p className="text-gray-600">서로의 초대 코드로 연결하고, 매주 대화 리포트를 받아보세요.</p>

      <section className="space-y-2 rounded-lg border p-4">
        <h2 className="font-semibold">초대 코드 만들기</h2>
        <button
          onClick={createInvite}
          className="rounded bg-rose-500 px-4 py-2 text-white hover:bg-rose-600"
        >
          코드 발급
        </button>
        {invite && (
          <p className="font-mono text-lg">
            {invite.invite_code} <span className="text-sm text-gray-500">(7일 유효)</span>
          </p>
        )}
      </section>

      <section className="space-y-2 rounded-lg border p-4">
        <h2 className="font-semibold">받은 코드 입력</h2>
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="예: K7P2M9QX"
            className="flex-1 rounded border px-3 py-2 font-mono"
            maxLength={8}
          />
          <button onClick={join} className="rounded bg-rose-500 px-4 py-2 text-white hover:bg-rose-600">
            연결
          </button>
        </div>
        {joined && <p>{joined.partner.display_name}님의 수락을 기다리는 중…</p>}
      </section>

      {error && <p className="text-sm text-red-500">{error}</p>}
    </main>
  );
}
