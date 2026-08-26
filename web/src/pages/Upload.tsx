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

function UploadHeroIllustration() {
  return (
    <div className="upload-hero-art" aria-hidden="true">
      <span className="upload-hero-art__halo" />
      <span className="upload-hero-art__heart upload-hero-art__heart--one">♥</span>
      <span className="upload-hero-art__heart upload-hero-art__heart--two">♡</span>
      <span className="upload-hero-art__sparkle upload-hero-art__sparkle--one">✦</span>
      <span className="upload-hero-art__sparkle upload-hero-art__sparkle--two">✧</span>
      <span className="upload-hero-art__bubble upload-hero-art__bubble--one">우리의 기록<br />차곡차곡</span>
      <span className="upload-hero-art__bubble upload-hero-art__bubble--two">우리</span>
      <svg className="upload-hero-art__illustration" viewBox="0 0 300 190" role="img" aria-label="대화 파일을 클라우드에 올리는 일러스트">
        <defs>
          <linearGradient id="upload-cloud-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fffefe" />
            <stop offset="1" stopColor="#ffe6ef" />
          </linearGradient>
          <linearGradient id="upload-file-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#eee5ff" />
            <stop offset="1" stopColor="#c9b3f0" />
          </linearGradient>
        </defs>
        <path d="M26 145c36-25 60-31 83-20 18 8 27 28 50 23 28-6 36-34 66-35 24-1 42 11 54 27" fill="none" stroke="#ffb0c5" strokeWidth="2" strokeDasharray="3 8" />
        <path d="M78 124c-18-2-29-14-29-28 0-16 14-29 31-29 5-19 22-32 42-32 22 0 40 16 43 37 18 0 32 12 32 28 0 15-13 27-29 27Z" fill="url(#upload-cloud-gradient)" stroke="#f2a7bd" strokeWidth="2.5" />
        <path d="M80 99h81M91 109h56" stroke="#e6b1c2" strokeWidth="3" strokeLinecap="round" opacity=".7" />
        <path d="M119 101V70m0 0-10 10m10-10 10 10" fill="none" stroke="#d08bb0" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M205 54h43l18 18v61a8 8 0 0 1-8 8h-53a8 8 0 0 1-8-8V62a8 8 0 0 1 8-8Z" fill="url(#upload-file-gradient)" stroke="#a589d4" strokeWidth="2.3" transform="rotate(7 232 97)" />
        <path d="m248 55 1 18 17-1" fill="#f8f2ff" stroke="#a589d4" strokeWidth="2" transform="rotate(7 232 97)" />
        <path d="M216 92h27M216 103h32M216 114h22" stroke="#8061a8" strokeWidth="2.5" strokeLinecap="round" opacity=".72" transform="rotate(7 232 97)" />
        <path d="M187 124c12-10 22-15 34-12 11 3 15 12 27 12 14 0 20-10 32-11" fill="none" stroke="#f28aaa" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

export default function Upload() {
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
    <main className="upload-page">
      <div className="upload-background-decor" aria-hidden="true">
        <span className="upload-decor-cloud upload-decor-cloud--one" />
        <span className="upload-decor-cloud upload-decor-cloud--two" />
        <span className="upload-decor-sparkle upload-decor-sparkle--one">✦</span>
        <span className="upload-decor-sparkle upload-decor-sparkle--two">✧</span>
        <span className="upload-decor-petal upload-decor-petal--one" />
        <span className="upload-decor-petal upload-decor-petal--two" />
        <span className="upload-decor-path" />
      </div>

      <header className="upload-hero">
        <div className="upload-hero__copy">
          <span className="upload-eyebrow">OUR CHAT ARCHIVE</span>
          <h1>우리의 대화를<br /><span>가져와볼까요?</span></h1>
          <p>카카오톡 대화 파일을 올리면<br className="upload-hero__break" /> 우리의 기록을 차근차근 정리해드려요.</p>
        </div>
        <div className="upload-hero__aside"><UploadHeroIllustration /></div>
      </header>

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
