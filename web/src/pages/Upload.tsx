// 역할: 업로드 — 드롭 → 내 카카오톡 이름 선택 → 진행률 (참조: FR-002, API_SPEC §3, TRD §6.2) — 시여 담당
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
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
  const location = useLocation();
  const navigate = useNavigate();
  const initialState = location.state as { initialFile?: File; redirectOnSuccess?: string } | null;
  const initialFile = initialState?.initialFile instanceof File ? initialState.initialFile : null;
  const redirectOnSuccessRef = useRef(
    typeof initialState?.redirectOnSuccess === "string" ? initialState.redirectOnSuccess : null,
  );
  const { data: coupleData } = useCoupleMe();
  const coupleId = coupleData?.couple_id;
  const activeJobId = coupleData?.active_job?.job_id ?? null;
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(initialFile);
  const [isDragging, setIsDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>(initialFile ? "mapping" : "idle");
  const [mappingOpen, setMappingOpen] = useState(Boolean(initialFile));
  const [mappingRequired, setMappingRequired] = useState(false);
  const [detectedSenders, setDetectedSenders] = useState<string[]>([]);
  const [selectedSelfSender, setSelectedSelfSender] = useState("");
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [trackedJobId, setTrackedJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialFile) navigate(location.pathname, { replace: true, state: null });
  }, [initialFile, location.pathname, navigate]);

  useEffect(() => {
    if (!trackedJobId && activeJobId && stage === "idle") {
      setTrackedJobId(activeJobId);
      setStage("processing");
    }
  }, [activeJobId, stage, trackedJobId]);

  const jobQuery = useQuery({
    queryKey: ["job", trackedJobId],
    queryFn: () => api.get<JobResponse>(`/api/jobs/${trackedJobId}`),
    enabled: Boolean(trackedJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 2_000;
    },
  });

  useEffect(() => {
    const nextJob = jobQuery.data;
    if (!nextJob) return;

    setJob(nextJob);
    if (nextJob.status === "done") {
      setStage("success");
      setTrackedJobId(null);
      if (redirectOnSuccessRef.current) navigate(redirectOnSuccessRef.current, { replace: true });
    } else if (nextJob.status === "failed") {
      setStage("error");
      setError("파일은 업로드되었지만 후속 처리가 실패했어요.");
      setTrackedJobId(null);
    } else {
      setStage("processing");
    }
  }, [jobQuery.data, navigate]);

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
    setSelectedSelfSender("");
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

    const form = new FormData();
    form.append("file", file);
    if (mappingRequired) {
      if (detectedSenders.length !== 2) {
        setError("파일에서 두 참여자의 이름을 확인하지 못했어요.");
        return;
      }
      if (!selectedSelfSender || !detectedSenders.includes(selectedSelfSender)) {
        setError("두 이름 중 내가 사용한 이름을 선택해주세요.");
        return;
      }
      if (!coupleData?.me) {
        setError("로그인한 사용자의 커플 정보를 확인하지 못했어요.");
        return;
      }

      const partnerSender = detectedSenders.find((sender) => sender !== selectedSelfSender);
      if (!partnerSender) {
        setError("상대방의 이름을 확인하지 못했어요.");
        return;
      }
      const nameMap = coupleData.me === "a"
        ? { a: selectedSelfSender, b: partnerSender }
        : { a: partnerSender, b: selectedSelfSender };
      form.append("name_map", JSON.stringify(nameMap));
    }

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
      setTrackedJobId(uploadResult.job_id);
    } catch (requestError) {
      if (requestError instanceof ApiClientError && requestError.code === "NAME_MAPPING_REQUIRED") {
        const senders = requestError.detail?.senders;
        setDetectedSenders(
          Array.isArray(senders) ? senders.filter((sender): sender is string => typeof sender === "string") : [],
        );
        setSelectedSelfSender("");
        setMappingRequired(true);
        setStage("mapping");
        setMappingOpen(true);
        setError(null);
      } else {
        setStage("error");
        setError(getErrorMessage(requestError));
      }
    }
  };

  const reset = () => {
    setFile(null);
    setStage("idle");
    setMappingOpen(false);
    setMappingRequired(false);
    setDetectedSenders([]);
    setSelectedSelfSender("");
    setResult(null);
    setJob(null);
    setTrackedJobId(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const percent = progressPercent(job);
  const isBusy = stage === "uploading" || stage === "processing";

  return (
    <main className="upload-page">
      {!file && !isBusy && (
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
              <p className="upload-file-card__mapping-title">대화 참여자를 확인해주세요</p>
              <p className="upload-file-card__mapping-copy">
                파일 속 두 사람을 확인한 뒤, 내가 사용한 카카오톡 이름을 선택해요.
              </p>
              <Button className="upload-file-card__mapping-button" onClick={() => setMappingOpen(true)}>
                참여자 확인 및 업로드
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
          <p className="upload-progress-card__warm-copy">
            처리 시간이 길어져도 계속 확인해요. 새로고침하거나 다시 방문해도 진행 상태가 복구돼요.
          </p>
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
        title={mappingRequired ? "카카오톡에서 내가 누구인가요?" : "대화 참여자를 확인할게요"}
        className="upload-mapping-modal"
      >
        <form className="upload-mapping-form" onSubmit={onUpload}>
          <p className="upload-mapping-form__intro">
            {mappingRequired
              ? "파일에서 찾은 두 이름 중 내가 사용한 이름 하나만 선택해주세요. 상대방은 자동으로 연결돼요."
              : "파일을 먼저 확인한 뒤, 대화에 표시된 두 이름을 보여드릴게요."}
          </p>
          {mappingRequired && coupleData?.me && coupleData.members && (
            <div className="upload-mapping-form__detected">
              현재 로그인한 계정: <strong>{coupleData.members[coupleData.me].display_name}</strong>
            </div>
          )}
          {mappingRequired && (
            <fieldset className="upload-mapping-form__identity">
              <legend>내 카카오톡 이름</legend>
              <div className="upload-mapping-form__partners">
                {detectedSenders.map((sender) => {
                  const selected = selectedSelfSender === sender;
                  return (
                    <label
                      key={sender}
                      className={`upload-partner-card${selected ? " is-selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name="self-sender"
                        value={sender}
                        checked={selected}
                        onChange={() => {
                          setSelectedSelfSender(sender);
                          setError(null);
                        }}
                      />
                      <span className="upload-partner-card__avatar" aria-hidden="true">
                        {sender.slice(0, 1)}
                      </span>
                      <span className="upload-partner-card__copy">
                        <strong>{sender}</strong>
                        <small>{selected ? "이 이름이 나예요" : "선택하기"}</small>
                      </span>
                      {selected && <span className="upload-partner-card__selected">나</span>}
                    </label>
                  );
                })}
              </div>
            </fieldset>
          )}
          {error && stage === "mapping" && (
            <p role="alert" className="upload-mapping-form__error">{error}</p>
          )}
          <div className="upload-mapping-form__actions">
            <Button type="button" variant="secondary" onClick={() => setMappingOpen(false)} disabled={isBusy}>
              닫기
            </Button>
            <Button type="submit" disabled={isBusy}>
              {mappingRequired ? "선택하고 업로드" : "참여자 확인"}
            </Button>
          </div>
        </form>
      </Modal>
    </main>
  );
}
