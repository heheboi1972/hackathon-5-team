// 역할: 업로드 — 드롭 → 이름 매핑 → 진행률 (참조: FR-002, TRD §6.2) — 시여 담당
// 스캐폴딩: 파일 선택 + 업로드 호출만. 이름 매핑 UI·useJob 폴링은 TODO(시여)
import { useState } from "react";
import { api } from "../api/client";
import type { UploadResponse } from "../api/types";

export default function Upload() {
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onFile = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      setResult(
        await api.postForm<UploadResponse>(
          "/api/couples/00000000-0000-0000-0000-000000000001/upload",
          form,
        ),
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <main className="mx-auto max-w-md space-y-4 p-8">
      <h1 className="text-2xl font-bold">대화 올리기</h1>
      <p className="text-gray-600">카카오톡 내보내기 파일(.txt / .zip)을 선택하세요.</p>
      <input
        type="file"
        accept=".txt,.zip"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
      {result && (
        <p className="text-sm text-gray-700">
          {result.parsed.message_count.toLocaleString()}개 메시지 · 새 메시지{" "}
          {result.parsed.new_messages}개 · 리포트 {result.report_jobs.total}주 생성 중
        </p>
      )}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </main>
  );
}
