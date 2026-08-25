// 역할: 업로드 — 드롭 → 이름 매핑 → 진행률 (참조: FR-002, API_SPEC §3, TRD §6.2) — 시여 담당
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiClientError, api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import Modal from "../components/Modal";
import type { JobResponse, UploadResponse } from "../api/types";

type UploadStage = "idle" | "mapping" | "uploading" | "processing" | "success" | "error";

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const COUPLE_ID = "00000000-0000-0000-0000-000000000001";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "업로드를 처리하지 못했어요.";
}

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".txt") || name.endsWith(".zip");
}

function progressPercent(job: JobResponse | null): number {
  if (!job || job.progress.total <= 0) return 0;
  return Math.min(100, Math.round((job.progress.done / job.progress.total) * 100));
}

export default function Upload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<UploadStage>("idle");
  const [mappingOpen, setMappingOpen] = useState(false);
  const [mappingRequired, setMappingRequired] = useState(false);
  const [detectedSenders, setDetectedSenders] = useState<string[]>([]);
  const [nameMap, setNameMap] = useState({ a: "", b: "" });
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const chooseFile = (candidate: File | undefined) => {
    if (!candidate) return;
    if (!isSupportedFile(candidate)) {
      setFile(null);
      setStage("error");
      setError("카카오톡 내보내기 파일은 .txt 또는 .zip 형식만 올릴 수 있어요.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null);
      setStage("error");
      setError("파일 크기는 50MB 이하만 가능해요.");
      return;
    }

    setFile(candidate);
    setStage("mapping");
    setMappingRequired(false);
    setDetectedSenders([]);
    setResult(null);
    setJob(null);
    setError(null);
    setMappingOpen(true);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    chooseFile(event.dataTransfer.files?.[0]);
  };

  const onUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;

    const a = nameMap.a.trim();
    const b = nameMap.b.trim();
    if ((a && !b) || (!a && b)) {
      setError("두 참여자의 이름을 모두 입력하거나, 둘 다 비워주세요.");
      return;
    }
    if (a && b && a === b) {
      setError("A와 B에는 서로 다른 참여자를 입력해주세요.");
      return;
    }
    if (mappingRequired && (!a || !b)) {
      setError("서버가 확인한 두 참여자를 A와 B에 각각 연결해주세요.");
      return;
    }

    const form = new FormData();
    form.append("file", file);
    if (a && b) form.append("name_map", JSON.stringify({ a, b }));

    setMappingOpen(false);
    setStage("uploading");
    setError(null);
    setResult(null);
    setJob(null);

    try {
      const uploadResult = await api.postForm<UploadResponse>(
        `/api/couples/${COUPLE_ID}/upload`,
        form,
      );
      setResult(uploadResult);
      setStage("processing");
      await pollJob(uploadResult.job_id);
    } catch (requestError) {
      if (requestError instanceof ApiClientError && requestError.code === "NAME_MAPPING_REQUIRED") {
        const senders = requestError.detail?.senders;
        setDetectedSenders(
          Array.isArray(senders) ? senders.filter((sender): sender is string => typeof sender === "string") : [],
        );
        setMappingRequired(true);
        setStage("mapping");
        setMappingOpen(true);
      } else {
        setStage("error");
      }
      setError(getErrorMessage(requestError));
    }
  };

  const pollJob = async (jobId: string) => {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const nextJob = await api.get<JobResponse>(`/api/jobs/${jobId}`);
      setJob(nextJob);
      if (nextJob.status === "done") {
        setStage("success");
        return;
      }
      if (nextJob.status === "failed") {
        setStage("error");
        setError("파일은 업로드되었지만 후속 처리가 실패했어요.");
        return;
      }
      setStage("processing");
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    setStage("error");
    setError("처리 상태를 확인하는 데 시간이 너무 오래 걸리고 있어요.");
  };

  const reset = () => {
    setFile(null);
    setStage("idle");
    setMappingOpen(false);
    setMappingRequired(false);
    setDetectedSenders([]);
    setNameMap({ a: "", b: "" });
    setResult(null);
    setJob(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const percent = progressPercent(job);
  const isBusy = stage === "uploading" || stage === "processing";

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <header className="space-y-2">
        <p className="text-sm font-medium text-rose-600">커플 대화 리포트</p>
        <h1 className="text-2xl font-bold text-gray-900">대화 파일 올리기</h1>
        <p className="text-gray-600">카카오톡 내보내기 파일을 올리면 대화 데이터를 정리해요.</p>
      </header>

      {!file && (
        <Card>
          <div
            className="rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-10 text-center transition-colors hover:border-rose-300 hover:bg-rose-50"
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop}
          >
            <p className="font-medium text-gray-800">파일을 이곳에 끌어다 놓으세요</p>
            <p className="mt-1 text-sm text-gray-500">또는 아래에서 파일을 선택하세요. .txt / .zip, 최대 50MB</p>
            <Button type="button" className="mt-5" onClick={() => inputRef.current?.click()}>
              파일 선택
            </Button>
            <input
              ref={inputRef}
              type="file"
              accept=".txt,.zip"
              className="sr-only"
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
          </div>
        </Card>
      )}

      {file && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Badge tone="neutral">선택한 파일</Badge>
              <h2 className="mt-2 break-all font-semibold text-gray-900">{file.name}</h2>
              <p className="mt-1 text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(2)}MB</p>
            </div>
            <Button variant="secondary" size="sm" onClick={reset} disabled={isBusy}>
              다른 파일 선택
            </Button>
          </div>
          {stage === "mapping" && (
            <div className="mt-5 rounded-lg bg-gray-50 p-4">
              <p className="font-medium text-gray-800">이름 매핑을 확인해주세요</p>
              <p className="mt-1 text-sm text-gray-600">
                처음 올리는 파일이거나 참여자를 찾지 못한 경우에만 입력하면 돼요.
              </p>
              <Button className="mt-4" onClick={() => setMappingOpen(true)}>
                이름 매핑 및 업로드
              </Button>
            </div>
          )}
        </Card>
      )}

      {isBusy && (
        <Card>
          <div className="flex items-center justify-between gap-4">
            <div>
              <Badge tone="neutral">{stage === "uploading" ? "업로드 중" : "처리 중"}</Badge>
              <h2 className="mt-2 font-semibold text-gray-900">
                {stage === "uploading" ? "파일을 분석하고 있어요" : "리포트를 준비하고 있어요"}
              </h2>
            </div>
            {job && <span className="text-sm font-medium text-gray-600">{percent}%</span>}
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-gray-200" aria-label="업로드 진행률">
            <div
              className={[
                "h-full rounded-full bg-rose-500 transition-all",
                stage === "uploading" ? "w-1/3 animate-pulse" : "",
              ].join(" ")}
              style={stage === "processing" ? { width: `${percent}%` } : undefined}
            />
          </div>
          {job && (
            <p className="mt-2 text-sm text-gray-600">
              주차 처리 {job.progress.done}/{job.progress.total}
              {job.current_week && ` · ${job.current_week}`}
            </p>
          )}
        </Card>
      )}

      {result && (stage === "success" || stage === "processing") && (
        <Card>
          <Badge tone={stage === "success" ? "neutral" : "b"}>
            {stage === "success" ? "업로드 완료" : "업로드 접수"}
          </Badge>
          <h2 className="mt-2 font-semibold text-gray-900">
            {result.parsed.message_count.toLocaleString()}개 메시지를 확인했어요
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            새 메시지 {result.parsed.new_messages.toLocaleString()}개 · 세션 {result.parsed.session_count.toLocaleString()}개 ·
            리포트 {result.report_jobs.total}주
          </p>
          {stage === "success" && (
            <Link to="/timeline" className="mt-4 inline-flex font-medium text-rose-600 hover:underline">
              타임라인 확인하기 →
            </Link>
          )}
        </Card>
      )}

      {stage === "error" && error && (
        <Card className="border-red-200 bg-red-50">
          <Badge tone="neutral">처리 실패</Badge>
          <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>
          {file && <Button className="mt-4" variant="secondary" onClick={() => setMappingOpen(true)}>다시 시도</Button>}
        </Card>
      )}

      {error && stage !== "error" && stage !== "mapping" && (
        <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      <Modal
        open={mappingOpen}
        onClose={() => !isBusy && setMappingOpen(false)}
        title="참여자 이름 매핑"
      >
        <form className="space-y-4" onSubmit={onUpload}>
          <p className="text-sm text-gray-600">
            카카오톡 파일의 두 참여자를 A와 B에 연결해주세요. 이름을 모르면 비워두고 먼저 업로드할 수 있어요.
          </p>
          {detectedSenders.length > 0 && (
            <div className="rounded bg-amber-50 p-3 text-sm text-amber-800">
              파일에서 확인된 참여자: {detectedSenders.join(", ")}
            </div>
          )}
          <label className="block space-y-1 text-sm font-medium text-gray-700">
            A 이름
            <input
              value={nameMap.a}
              onChange={(event) => setNameMap((current) => ({ ...current, a: event.target.value }))}
              className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
              placeholder="카카오톡 이름"
            />
          </label>
          <label className="block space-y-1 text-sm font-medium text-gray-700">
            B 이름
            <input
              value={nameMap.b}
              onChange={(event) => setNameMap((current) => ({ ...current, b: event.target.value }))}
              className="w-full rounded border px-3 py-2 font-normal outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
              placeholder="카카오톡 이름"
            />
          </label>
          {error && stage === "mapping" && (
            <p role="alert" className="text-sm text-red-700">{error}</p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setMappingOpen(false)} disabled={isBusy}>
              닫기
            </Button>
            <Button type="submit" disabled={isBusy}>
              업로드 시작
            </Button>
          </div>
        </form>
      </Modal>
    </main>
  );
}
