// 역할: 업로드 — 드롭 → 이름 매핑 → 진행률 (참조: FR-002, API_SPEC §3, TRD §6.2) — 시여 담당
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiClientError, api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import Modal from "../components/Modal";
import { useCoupleMe } from "../hooks/useCoupleMe";
import type { JobResponse, UploadResponse } from "../api/types";

type UploadStage = "idle" | "mapping" | "uploading" | "processing" | "success" | "error";

const MAX_FILE_SIZE = 50 * 1024 * 1024;

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
  const { data: coupleData } = useCoupleMe();
  const coupleId = coupleData?.couple_id;
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
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
    setIsDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  };

  const onUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    if (!coupleId) {
      setStage("error");
      setError("연결된 커플 정보를 확인할 수 없습니다.");
      return;
    }

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
        `/api/couples/${coupleId}/upload`,
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
    <main className="upload-page">
      {!file && (
        <Card className="upload-drop-card">
          <div
            className={`upload-dropzone${isDragging ? " upload-dropzone--dragging" : ""}`}
            onDragEnter={() => setIsDragging(true)}
            onDragLeave={() => setIsDragging(false)}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDrop={onDrop}
          >
            <div className="upload-dropzone__icon" aria-hidden="true">
              <svg viewBox="0 0 48 48"><path d="M14 31.5h21a7 7 0 0 0 .7-14A10.5 10.5 0 0 0 15 20.2 5.7 5.7 0 0 0 14 31.5Z" /><path d="M24 30V18m0 0-4 4m4-4 4 4" /></svg>
            </div>
            <p className="upload-dropzone__title">대화 파일을 여기에 올려주세요</p>
            <p className="upload-dropzone__hint">.txt 또는 .zip <span>·</span> 최대 50MB</p>
            <Button type="button" className="upload-dropzone__button" onClick={() => inputRef.current?.click()}>
              파일 선택하기 <span aria-hidden="true">↗</span>
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
        <Card className="upload-file-card">
          <div className="upload-file-card__topline">
            <span className="upload-file-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M6 3.5h8l4 4v13H6z" /><path d="M14 3.5v4h4M9 12h6M9 15.5h4" /></svg>
            </span>
            <div className="upload-file-card__copy">
              <Badge tone="neutral">선택한 파일</Badge>
              <h2>{file.name}</h2>
              <p>{(file.size / 1024 / 1024).toFixed(2)}MB <span>·</span> {file.name.split(".").pop()?.toUpperCase() ?? "FILE"}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={reset} disabled={isBusy}>
              다른 파일
            </Button>
          </div>
          {stage === "mapping" && (
            <div className="upload-file-card__mapping">
              <p className="upload-file-card__mapping-title">이름 매핑을 확인해주세요</p>
              <p className="upload-file-card__mapping-copy">
                처음 올리는 파일이거나 참여자를 찾지 못한 경우에만 입력하면 돼요.
              </p>
              <Button className="upload-file-card__mapping-button" onClick={() => setMappingOpen(true)}>
                이름 매핑 및 업로드
              </Button>
            </div>
          )}
        </Card>
      )}

      {isBusy && (
        <Card className="upload-progress-card">
          <div className="upload-progress-card__heading">
            <span className="upload-progress-card__icon" aria-hidden="true">✦</span>
            <div>
              <Badge tone="neutral">{stage === "uploading" ? "업로드 중" : "처리 중"}</Badge>
              <h2>
                {stage === "uploading" ? "파일을 분석하고 있어요" : "리포트를 준비하고 있어요"}
              </h2>
            </div>
            {job && <span className="upload-progress-card__percent">{percent}%</span>}
          </div>
          <p className="upload-progress-card__warm-copy">우리의 대화를 정리하고 있어요 ✨</p>
          <div className="upload-progress-card__bar" aria-label="업로드 진행률">
            <div
              className={[
                "upload-progress-card__bar-fill",
                stage === "uploading" ? "upload-progress-card__bar-fill--uploading" : "",
              ].join(" ")}
              style={stage === "processing" ? { width: `${percent}%` } : undefined}
            />
          </div>
          {job && (
            <p className="upload-progress-card__detail">
              주차 처리 {job.progress.done}/{job.progress.total}
              {job.current_week && ` · ${job.current_week}`}
            </p>
          )}
        </Card>
      )}

      {result && (stage === "success" || stage === "processing") && (
        <Card className={`upload-result-card${stage === "success" ? " upload-result-card--success" : ""}`}>
          <div className="upload-result-card__heading">
            <span className="upload-result-card__icon" aria-hidden="true">{stage === "success" ? "♥" : "✦"}</span>
            <div>
              <Badge tone={stage === "success" ? "neutral" : "b"}>
            {stage === "success" ? "업로드 완료" : "업로드 접수"}
              </Badge>
              {stage === "success" && <p className="upload-result-card__kicker">대화 준비가 완료됐어요</p>}
            </div>
          </div>
          <h2>
            {result.parsed.message_count.toLocaleString()}개 메시지를 확인했어요
          </h2>
          <p className="upload-result-card__summary">
            새 메시지 {result.parsed.new_messages.toLocaleString()}개 · 세션 {result.parsed.session_count.toLocaleString()}개 ·
            리포트 {result.report_jobs.total}주
          </p>
          {stage === "success" && (
            <Link to="/timeline" className="upload-result-card__link">
              타임라인 확인하기 →
            </Link>
          )}
        </Card>
      )}

      {stage === "error" && error && (
        <Card className="upload-error-card">
          <div className="upload-error-card__heading"><span aria-hidden="true">!</span><Badge tone="neutral">처리 실패</Badge></div>
          <p role="alert">{error}</p>
          {file && <Button className="upload-error-card__button" variant="secondary" onClick={() => setMappingOpen(true)}>다시 시도</Button>}
        </Card>
      )}

      {error && stage !== "error" && stage !== "mapping" && (
        <p role="alert" className="upload-inline-error">{error}</p>
      )}

      <Modal
        open={mappingOpen}
        onClose={() => !isBusy && setMappingOpen(false)}
        title="누가 누구인지 알려주세요"
        className="upload-mapping-modal"
      >
        <form className="upload-mapping-form" onSubmit={onUpload}>
          <p className="upload-mapping-form__intro">
            카카오톡 파일의 두 참여자를 A와 B에 연결해주세요. 이름을 모르면 비워두고 먼저 업로드할 수 있어요.
          </p>
          {detectedSenders.length > 0 && (
            <div className="upload-mapping-form__detected">
              파일에서 확인된 참여자: {detectedSenders.join(", ")}
            </div>
          )}
          <div className="upload-mapping-form__partners">
          <label className="upload-partner-card upload-partner-card--a">
            <span className="upload-partner-card__avatar" aria-hidden="true">A</span>
            <span className="upload-partner-card__label">발화자 A</span>
            <input
              value={nameMap.a}
              onChange={(event) => setNameMap((current) => ({ ...current, a: event.target.value }))}
              className="upload-partner-card__input"
              placeholder="카카오톡 이름"
            />
          </label>
          <label className="upload-partner-card upload-partner-card--b">
            <span className="upload-partner-card__avatar" aria-hidden="true">B</span>
            <span className="upload-partner-card__label">발화자 B</span>
            <input
              value={nameMap.b}
              onChange={(event) => setNameMap((current) => ({ ...current, b: event.target.value }))}
              className="upload-partner-card__input"
              placeholder="카카오톡 이름"
            />
          </label>
          </div>
          {error && stage === "mapping" && (
            <p role="alert" className="upload-mapping-form__error">{error}</p>
          )}
          <div className="upload-mapping-form__actions">
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
