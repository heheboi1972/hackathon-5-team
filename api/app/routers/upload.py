"""FR-002 카카오톡 업로드의 동기 처리 구간."""

from __future__ import annotations

import asyncio
import hashlib
import json
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date, timezone
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from ..deps import AuthenticatedUser, current_user
from ..models.api import DateRange, JobRef, ParsedInfo, ReportJobsInfo, UploadResponse
from ..services.kakao_parser import (
    Message,
    classify,
    parse_export_with_format,
    tokenize,
)
from ..services.metrics import (
    build_weekly_metrics,
    count_terms,
    split_sessions,
    week_start_of,
)
from ..services.postgres_service import RepositoryError

router = APIRouter(prefix="/api", tags=["upload"])
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _error(
    status_code: int, code: str, message: str, detail: dict[str, Any] | None = None
) -> HTTPException:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return HTTPException(status_code=status_code, detail=body)


def _parse(data: bytes) -> tuple[str, list[Message]]:
    fmt, messages = parse_export_with_format(data)
    if not messages:
        raise ValueError("메시지를 찾을 수 없습니다")
    return fmt, messages


def _resolve_name_map(
    raw: str | None, senders: set[str], stored: dict[str, str] | None
) -> dict[str, str]:
    if raw:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("name_map은 JSON 객체여야 합니다") from exc
        if not isinstance(value, dict) or set(value) != {"a", "b"}:
            raise ValueError("두 참여자의 이름 정보가 모두 필요합니다")
        result = {"a": str(value["a"]).strip(), "b": str(value["b"]).strip()}
        if (
            not all(result.values())
            or len(set(result.values())) != 2
            or set(result.values()) != senders
        ):
            raise ValueError(
                "선택한 이름은 파일에서 감지된 두 참여자와 정확히 일치해야 합니다"
            )
        return result
    if stored and set(stored.values()) == senders:
        return stored
    raise LookupError("name mapping required")


def _map_senders(messages: list[Message], mapping: dict[str, str]) -> list[Message]:
    reverse = {name: role for role, name in mapping.items()}
    return [
        Message(
            sender=reverse[m.sender],
            sent_at=m.sent_at,
            body=m.body,
            msg_type=m.msg_type,
            is_question=m.is_question,
            body_len=m.body_len,
            tokens=m.tokens,
        )
        for m in messages
    ]


def _normalize_hash_body(body: str) -> str:
    normalized = unicodedata.normalize("NFC", body).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def _message_hash(message: Message) -> str:
    # PC·모바일 내보내기의 초 정밀도 차이를 제거한다 (ISSUE C5).
    minute = (
        message.sent_at.astimezone(timezone.utc)
        .replace(second=0, microsecond=0)
        .isoformat(timespec="minutes")
    )
    canonical = json.dumps(
        [message.sender.strip().lower(), minute, _normalize_hash_body(message.body)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stored_messages(rows: list[dict[str, Any]], decrypt: Any) -> list[Message]:
    out: list[Message] = []
    for row in rows:
        body = decrypt(row["body_enc"])
        msg_type = classify(body)
        out.append(
            Message(
                sender=row["sender"],
                sent_at=row["sent_at"],
                body=body,
                msg_type=msg_type,
                is_question=row["is_question"],
                body_len=row["body_len"],
                tokens=tokenize(body) if msg_type == "text" else [],
            )
        )
    return out


def _week_payloads(
    messages: list[Message], gap_min: int, lexicon: dict[str, tuple[str, str]]
):
    sessions = split_sessions(messages, gap_min)
    computed = build_weekly_metrics(messages, "a", "b", gap_min)
    by_week: dict[Any, list[Message]] = defaultdict(list)
    for message in messages:
        by_week[week_start_of(message.sent_at.date())].append(message)

    weeks: list[dict[str, Any]] = []
    for week in computed:
        week_start = date.fromisoformat(week["week_start"])
        current_metrics = {
            key: {axis: metric.get(axis) for axis in ("couple", "a", "b")}
            for key, metric in week["metrics"].items()
        }
        summary = {
            "session_count": week["session_count"],
            "message_count": week["message_count"],
            **current_metrics,
            **week["summary_extras"],
        }
        summary_json = json.dumps(
            summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        term_counts = count_terms(by_week[week_start], lexicon)
        terms = [
            {
                "week_start": week_start,
                "sender": sender,
                "canonical": canonical,
                "polarity": polarity,
                "count": count,
            }
            for (sender, canonical, polarity), count in term_counts.items()
        ]
        weeks.append(
            {
                "week_start": week_start,
                "summary": summary,
                "metrics": week["metrics"],
                "summary_hash": hashlib.sha256(
                    summary_json.encode("utf-8")
                ).hexdigest(),
                "outliers": week["outliers"],
                "terms": terms,
            }
        )
    session_rows = [
        {
            "session_id": s.session_id,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "initiator": s.initiator,
            "msg_count": s.msg_count,
        }
        for s in sessions
    ]
    return session_rows, weeks


@router.post(
    "/couples/{couple_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    couple_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(current_user),
    file: UploadFile = File(...),
    name_map: str | None = Form(default=None),
) -> UploadResponse:
    container = request.app.state.container
    couple = await container.postgres.get_active_couple(couple_id, user.user_id)
    if couple is None or couple["member"] is None or couple["status"] != "active":
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "COUPLE_NOT_ACTIVE",
            "활성 커플만 업로드할 수 있습니다",
        )

    suffix = (file.filename or "").lower()
    if not suffix.endswith((".txt", ".zip")):
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "UNSUPPORTED_FORMAT",
            ".txt 또는 .zip 파일만 지원합니다",
        )
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "FILE_TOO_LARGE",
            "파일은 최대 50MB까지 업로드할 수 있습니다",
        )
    try:
        fmt, parsed_messages = await asyncio.to_thread(_parse, data)
    except (UnicodeDecodeError, ValueError, zipfile.BadZipFile) as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "UNSUPPORTED_FORMAT", str(exc)
        ) from exc

    senders = {m.sender for m in parsed_messages}
    if len(senders) != 2:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "NOT_COUPLE_CHAT",
            "두 명의 대화만 업로드할 수 있습니다",
            {"senders": sorted(senders)},
        )
    stored_mapping = None
    if couple["kakao_name_a"] and couple["kakao_name_b"]:
        stored_mapping = {"a": couple["kakao_name_a"], "b": couple["kakao_name_b"]}
    try:
        mapping = _resolve_name_map(name_map, senders, stored_mapping)
    except LookupError as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "NAME_MAPPING_REQUIRED",
            "두 참여자 중 내가 사용한 이름을 선택해주세요",
            {"senders": sorted(senders)},
        ) from exc
    except ValueError as exc:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "VALIDATION_ERROR", str(exc)
        ) from exc

    normalized = _map_senders(parsed_messages, mapping)
    stored_rows = await container.postgres.get_stored_messages(couple_id)
    # DB hash는 동시성 검증에 사용한다. 중복 판별은 과거 hash 규칙으로 저장된
    # 행도 안전하게 처리하도록 복호화한 기존 메시지에 현재 canonical 규칙을 적용한다.
    stored_db_hashes = {str(row["msg_hash"]).strip() for row in stored_rows}
    existing_messages = await asyncio.to_thread(
        _stored_messages, stored_rows, container.cipher.decrypt
    )
    seen = {_message_hash(message) for message in existing_messages}
    new_pairs: list[tuple[str, Message]] = []
    for message in normalized:
        digest = _message_hash(message)
        if digest not in seen:
            seen.add(digest)
            new_pairs.append((digest, message))

    all_messages = sorted(
        existing_messages + [m for _, m in new_pairs], key=lambda m: m.sent_at
    )
    lexicon = dict(container.knowledge.seed_lexicon)
    lexicon.update(await container.postgres.get_couple_lexicon(couple_id))
    sessions, weeks = await asyncio.to_thread(
        _week_payloads, all_messages, container.settings.session_gap_min, lexicon
    )
    new_rows = [
        {
            "msg_hash": digest,
            "sender": message.sender,
            "sent_at": message.sent_at,
            "body_enc": container.cipher.encrypt(message.body),
            "body_len": message.body_len,
            "is_question": message.is_question,
            "msg_type": message.msg_type,
        }
        for digest, message in new_pairs
    ]
    changed_week_starts = {
        week_start_of(row["sent_at"].date()) for row in new_rows
    }
    weeks_to_update = [w for w in weeks if w["week_start"] in changed_week_starts]
    try:
        result = await container.postgres.apply_upload(
            couple_id,
            user_id=user.user_id,
            base_hashes=stored_db_hashes,
            kakao_names=mapping,
            new_messages=new_rows,
            sessions=sessions,
            weeks=weeks_to_update,
        )
    except RepositoryError as exc:
        code_status = (
            status.HTTP_403_FORBIDDEN
            if exc.code == "COUPLE_NOT_ACTIVE"
            else status.HTTP_409_CONFLICT
        )
        raise _error(code_status, exc.code, exc.message) from exc

    first_date = min(message.sent_at.date() for message in normalized)
    last_date = max(message.sent_at.date() for message in normalized)

    return UploadResponse(
        job_id=str(result["report_job_id"]),
        embed_job=JobRef(job_id=str(result["embed_job_id"])),
        parsed=ParsedInfo(
            format=fmt,
            message_count=len(normalized),
            new_messages=len(new_rows),
            session_count=len(sessions),
            range=DateRange.model_validate({"from": first_date, "to": last_date}),
        ),
        weeks_computed=len(weeks),
        report_jobs=ReportJobsInfo(
            total=len(result["changed_weeks"]), pending=len(result["changed_weeks"])
        ),
    )
