"""Postgres 연결 풀과 Phase 2 저장소 연산.

ORM 없이 SQL을 명시적으로 유지한다. 상태 전이와 업로드는 각각 하나의
트랜잭션이며, 사용자/커플 advisory lock으로 중복 요청도 직렬화한다.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class PostgresService:
    def __init__(self, dsn: str):
        self.pool = AsyncConnectionPool(dsn, min_size=1, max_size=5, open=False)

    async def open(self, timeout: float = 10.0) -> None:
        await self.pool.open()
        await self.pool.wait(timeout=timeout)

    async def close(self) -> None:
        await self.pool.close()

    async def ping(self) -> bool:
        try:
            async with self.pool.connection(timeout=3) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as exc:
            logger.warning("postgres ping 실패: %s", exc)
            return False

    @staticmethod
    async def _lock(conn: Any, value: UUID) -> None:
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(value),)
        )

    # ---------------------------------------------------------------- auth

    async def create_user(
        self, email: str, password_hash: str, display_name: str
    ) -> UUID | None:
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO users (email, password_hash, display_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                    RETURNING user_id
                    """,
                    (email, password_hash, display_name),
                )
            ).fetchone()
        return row[0] if row else None

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                "SELECT user_id, email, password_hash, display_name FROM users WHERE email = %s",
                (email,),
            )
            return await cur.fetchone()

    async def get_user_context(self, user_id: UUID) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT u.user_id, u.email, u.display_name,
                       c.couple_id,
                       CASE WHEN c.user_a = u.user_id THEN 'a'
                            WHEN c.user_b = u.user_id THEN 'b' END AS member,
                       c.status AS couple_status
                  FROM users u
                  LEFT JOIN LATERAL (
                    SELECT couple_id, user_a, user_b, status
                      FROM couples
                     WHERE (user_a = u.user_id OR user_b = u.user_id)
                       AND status <> 'dissolved'
                     ORDER BY created_at DESC
                     LIMIT 1
                  ) c ON true
                 WHERE u.user_id = %s
                """,
                (user_id,),
            )
            return await cur.fetchone()

    # -------------------------------------------------------------- couples

    async def create_or_get_invite(
        self, user_id: UUID, invite_code: str, expires_at: datetime
    ) -> dict[str, Any]:
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, user_id)
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT couple_id FROM couples
                     WHERE (user_a = %s OR user_b = %s)
                       AND status IN ('active', 'awaiting_confirm')
                     LIMIT 1
                    """,
                    (user_id, user_id),
                )
                if await cur.fetchone():
                    raise RepositoryError(
                        "ALREADY_COUPLED", "이미 연결 중인 커플이 있습니다"
                    )

                await cur.execute(
                    """
                    SELECT couple_id, invite_code, invite_expires_at AS expires_at, status
                      FROM couples
                     WHERE user_a = %s AND status = 'pending'
                     ORDER BY created_at DESC LIMIT 1 FOR UPDATE
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
                if row:
                    if row["expires_at"] is None or row["expires_at"] <= datetime.now(
                        row["expires_at"].tzinfo
                    ):
                        await cur.execute(
                            """
                            UPDATE couples SET invite_code = %s, invite_expires_at = %s
                             WHERE couple_id = %s
                             RETURNING couple_id, invite_code, invite_expires_at AS expires_at, status
                            """,
                            (invite_code, expires_at, row["couple_id"]),
                        )
                        row = await cur.fetchone()
                    return row

                await cur.execute(
                    """
                    INSERT INTO couples (user_a, invite_code, invite_expires_at)
                    VALUES (%s, %s, %s)
                    RETURNING couple_id, invite_code, invite_expires_at AS expires_at, status
                    """,
                    (user_id, invite_code, expires_at),
                )
                return await cur.fetchone()

    async def join_invite(self, user_id: UUID, invite_code: str) -> dict[str, Any]:
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, user_id)
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT c.couple_id, c.user_a, c.status, c.invite_expires_at,
                           u.display_name AS partner_name
                      FROM couples c JOIN users u ON u.user_id = c.user_a
                     WHERE c.invite_code = %s
                     FOR UPDATE OF c
                    """,
                    (invite_code.upper(),),
                )
                invite = await cur.fetchone()
                if not invite or invite["invite_expires_at"] is None:
                    raise RepositoryError(
                        "INVITE_INVALID", "유효하지 않은 초대 코드입니다"
                    )
                now = datetime.now(invite["invite_expires_at"].tzinfo)
                if invite["invite_expires_at"] <= now:
                    raise RepositoryError("INVITE_INVALID", "만료된 초대 코드입니다")
                if invite["user_a"] == user_id:
                    raise RepositoryError(
                        "INVITE_SELF", "자신의 초대 코드에는 참여할 수 없습니다"
                    )
                if invite["status"] != "pending":
                    raise RepositoryError(
                        "INVITE_STATE", "참여할 수 없는 초대 상태입니다"
                    )

                await cur.execute(
                    """
                    SELECT 1 FROM couples
                     WHERE (user_a = %s OR user_b = %s) AND status <> 'dissolved'
                     LIMIT 1
                    """,
                    (user_id, user_id),
                )
                if await cur.fetchone():
                    raise RepositoryError(
                        "ALREADY_COUPLED", "이미 커플에 속해 있습니다"
                    )

                await cur.execute(
                    """
                    UPDATE couples SET user_b = %s, status = 'awaiting_confirm'
                     WHERE couple_id = %s AND status = 'pending'
                     RETURNING couple_id, status
                    """,
                    (user_id, invite["couple_id"]),
                )
                row = await cur.fetchone()
                if not row:
                    raise RepositoryError("INVITE_STATE", "초대 상태가 변경되었습니다")
                return {**row, "partner_name": invite["partner_name"]}

    async def confirm_couple(
        self, couple_id: UUID, user_id: UUID, accept: bool
    ) -> dict[str, Any]:
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, couple_id)
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT couple_id, user_a, status FROM couples WHERE couple_id = %s FOR UPDATE",
                    (couple_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise RepositoryError("NOT_FOUND", "커플을 찾을 수 없습니다")
                if row["user_a"] != user_id:
                    raise RepositoryError(
                        "FORBIDDEN", "초대를 만든 사용자만 확인할 수 있습니다"
                    )
                if row["status"] != "awaiting_confirm":
                    raise RepositoryError(
                        "INVITE_STATE", "확인할 수 없는 초대 상태입니다"
                    )
                if accept:
                    await cur.execute(
                        "UPDATE couples SET status = 'active' WHERE couple_id = %s RETURNING couple_id, status",
                        (couple_id,),
                    )
                else:
                    await cur.execute(
                        """
                        UPDATE couples SET status = 'pending', user_b = NULL
                         WHERE couple_id = %s RETURNING couple_id, status
                        """,
                        (couple_id,),
                    )
                return await cur.fetchone()

    async def get_couple_me(self, user_id: UUID) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT c.couple_id, c.status, c.user_a, c.user_b,
                       ua.display_name AS display_name_a, ub.display_name AS display_name_b,
                       c.kakao_name_a, c.kakao_name_b, c.started_at,
                       CASE WHEN c.user_a = %s THEN 'a' ELSE 'b' END AS me,
                       (SELECT min(date_trunc('week', m.sent_at)::date) FROM messages m WHERE m.couple_id=c.couple_id) AS first_week,
                       (SELECT max(date_trunc('week', m.sent_at)::date) FROM messages m WHERE m.couple_id=c.couple_id) AS last_week,
                       (SELECT count(*) FROM weekly_metrics w WHERE w.couple_id=c.couple_id) AS weeks_available,
                       (SELECT count(*) FROM messages m WHERE m.couple_id=c.couple_id) AS message_count,
                       j.job_id AS active_job_id, j.kind AS active_job_kind,
                       j.done AS active_job_done, j.total AS active_job_total
                  FROM couples c
                  JOIN users ua ON ua.user_id = c.user_a
                  LEFT JOIN users ub ON ub.user_id = c.user_b
                  LEFT JOIN LATERAL (
                    SELECT job_id, kind, done, total FROM jobs
                     WHERE couple_id=c.couple_id AND status IN ('queued','running')
                     ORDER BY created_at DESC LIMIT 1
                  ) j ON true
                 WHERE (c.user_a=%s OR c.user_b=%s) AND c.status <> 'dissolved'
                 ORDER BY c.created_at DESC LIMIT 1
                """,
                (user_id, user_id, user_id),
            )
            return await cur.fetchone()

    async def get_active_couple(
        self, couple_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT couple_id, status, user_a, user_b, kakao_name_a, kakao_name_b,
                       CASE WHEN user_a=%s THEN 'a' WHEN user_b=%s THEN 'b' END AS member
                  FROM couples WHERE couple_id=%s
                """,
                (user_id, user_id, couple_id),
            )
            return await cur.fetchone()

    # -------------------------------------------------------------- timeline

    async def get_timeline(
        self,
        couple_id: UUID,
        *,
        from_: date | None = None,
        to: date | None = None,
    ) -> list[dict[str, Any]]:
        """weekly_metrics 저장형을 Timeline 투영 입력으로 조립한다."""
        filters = ["wm.couple_id = %s"]
        params: list[Any] = [couple_id]
        if from_ is not None:
            filters.append("wm.week_start >= %s")
            params.append(from_)
        if to is not None:
            filters.append("wm.week_start <= %s")
            params.append(to)

        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                f"""
                SELECT wm.week_start,
                       wm.summary,
                       jsonb_array_length(wm.outliers) AS outlier_count,
                       coalesce(r.status, 'pending') AS report_status
                  FROM weekly_metrics wm
                  LEFT JOIN reports r
                    ON r.couple_id = wm.couple_id
                   AND r.week_start = wm.week_start
                 WHERE {' AND '.join(filters)}
                 ORDER BY wm.week_start ASC
                """,
                params,
            )
            rows = list(await cur.fetchall())
            if not rows:
                return []

            first_week = rows[0]["week_start"]
            last_week = rows[-1]["week_start"]
            await cur.execute(
                """
                SELECT week_start, sender, canonical, polarity, count
                  FROM weekly_terms
                 WHERE couple_id = %s
                   AND week_start >= %s
                   AND week_start <= %s
                   AND count >= 3
                 ORDER BY week_start, sender, polarity, count DESC, canonical
                """,
                (couple_id, first_week, last_week),
            )
            term_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT at, kind, label
                  FROM events
                 WHERE couple_id = %s
                   AND at >= %s
                   AND at < %s
                 ORDER BY at, event_id
                """,
                (couple_id, first_week, last_week + timedelta(days=7)),
            )
            event_rows = await cur.fetchall()

        terms_by_week: dict[date, dict[str, dict[str, list[dict[str, Any]]]]] = {}
        for term in term_rows:
            sender_terms = terms_by_week.setdefault(term["week_start"], {}).setdefault(
                term["sender"], {"pos": [], "neg": []}
            )
            polarity_terms = sender_terms[term["polarity"]]
            if len(polarity_terms) < 3:
                polarity_terms.append(
                    {"canonical": term["canonical"], "count": term["count"]}
                )

        events_by_week: dict[date, list[dict[str, Any]]] = {}
        for event in event_rows:
            week_start = event["at"] - timedelta(days=event["at"].weekday())
            events_by_week.setdefault(week_start, []).append(
                {"at": event["at"], "kind": event["kind"], "label": event["label"]}
            )

        return [
            {
                **row,
                "weekly_terms": terms_by_week.get(row["week_start"], {}),
                "events": events_by_week.get(row["week_start"], []),
            }
            for row in rows
        ]

    async def dissolve_couple(self, couple_id: UUID, user_id: UUID) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, couple_id)
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT user_a, user_b FROM couples WHERE couple_id=%s FOR UPDATE",
                    (couple_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise RepositoryError("NOT_FOUND", "커플을 찾을 수 없습니다")
                if user_id not in (row["user_a"], row["user_b"]):
                    raise RepositoryError("FORBIDDEN", "이 커플의 멤버가 아닙니다")
                await cur.execute(
                    "DELETE FROM couples WHERE couple_id=%s", (couple_id,)
                )

    # ---------------------------------------------------------------- jobs

    async def recover_running_jobs(self) -> int:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """
                UPDATE jobs SET status='queued', error=NULL, updated_at=now()
                 WHERE status='running'
                """
            )
            return cur.rowcount

    async def create_job(self, couple_id: UUID, kind: str, total: int = 0) -> UUID:
        initial = "done" if total == 0 else "queued"
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    """
                    INSERT INTO jobs (couple_id, kind, status, total)
                    VALUES (%s, %s, %s, %s) RETURNING job_id
                    """,
                    (couple_id, kind, initial, total),
                )
            ).fetchone()
            return row[0]

    async def get_job_for_user(
        self, job_id: UUID, user_id: UUID
    ) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT j.job_id, j.kind, j.status, j.total, j.done, j.failed, j.current_week
                  FROM jobs j JOIN couples c ON c.couple_id=j.couple_id
                 WHERE j.job_id=%s AND (c.user_a=%s OR c.user_b=%s)
                """,
                (job_id, user_id, user_id),
            )
            return await cur.fetchone()

    async def claim_next_job(self, kinds: Sequence[str]) -> dict[str, Any] | None:
        if not kinds:
            return None
        async with (
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                WITH picked AS (
                    SELECT job_id FROM jobs
                     WHERE status='queued' AND kind = ANY(%s::text[])
                     ORDER BY CASE kind WHEN 'embed_sessions' THEN 0 ELSE 1 END,
                              created_at, job_id
                     FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE jobs j SET status='running', updated_at=now()
                  FROM picked WHERE j.job_id=picked.job_id
                RETURNING j.*
                """,
                (list(kinds),),
            )
            return await cur.fetchone()

    async def update_job_progress(
        self, job_id: UUID, *, done: int, failed: int, current_week: date | None = None
    ) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """
                UPDATE jobs SET done=%s, failed=%s, current_week=%s, updated_at=now()
                 WHERE job_id=%s
                """,
                (done, failed, current_week, job_id),
            )

    async def finish_job(self, job_id: UUID, *, error: str | None = None) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """
                UPDATE jobs
                   SET status=%s, error=%s,
                       done=CASE WHEN %s IS NULL THEN total ELSE done END,
                       failed=CASE WHEN %s IS NULL THEN failed ELSE greatest(failed, 1) END,
                       updated_at=now()
                 WHERE job_id=%s
                """,
                ("done" if error is None else "failed", error, error, error, job_id),
            )

    # --------------------------------------------------------------- upload

    async def get_message_hashes(self, couple_id: UUID) -> set[str]:
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT msg_hash FROM messages WHERE couple_id=%s", (couple_id,)
                )
            ).fetchall()
            return {row[0] for row in rows}

    async def get_stored_messages(self, couple_id: UUID) -> list[dict[str, Any]]:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT sender, sent_at, body_enc, body_len, is_question, msg_hash
                  FROM messages WHERE couple_id=%s ORDER BY sent_at, message_id
                """,
                (couple_id,),
            )
            return list(await cur.fetchall())

    async def get_messages_for_embedding(self, couple_id: UUID) -> list[dict[str, Any]]:
        """embed_sessions 잡(TASKS 2-6, services/embed_sessions.py)용.
        session_id 가 배정된 메시지만 반환 — session_id IS NULL 인 메시지는 세션 재구성 전 상태라 대상이 아니다."""
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT session_id, sender, sent_at, body_enc, body_len, is_question
                  FROM messages
                 WHERE couple_id=%s AND session_id IS NOT NULL
                 ORDER BY session_id, sent_at
                """,
                (couple_id,),
            )
            return list(await cur.fetchall())

    async def get_messages_in_sessions(
        self, couple_id: UUID, session_ids: Sequence[int]
    ) -> list[dict[str, Any]]:
        """search_conversation 툴(TASKS 3-1)용 — 벡터 검색으로 고른 세션들의 본문만 가져온다.
        Qdrant payload 에는 본문·발화자가 없어서(프라이버시) 인용 카드는 여기서 복호화해 만든다."""
        if not session_ids:
            return []
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT session_id, sender, sent_at, body_enc, body_len, is_question
                  FROM messages
                 WHERE couple_id=%s AND session_id = ANY(%s)
                 ORDER BY session_id, sent_at
                """,
                (couple_id, list(session_ids)),
            )
            return list(await cur.fetchall())

    async def get_weekly_metrics(
        self,
        couple_id: UUID,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        """주 오름차순 weekly_metrics 행. 기준선은 저장돼 있지 않다 —
        upload 는 현재값만 넣고(summary_hash 안정성), 직전 4주 평균은 조회 시점에 계산한다
        (metrics.metrics_from_stored)."""
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT week_start, summary, summary_hash, outliers
                  FROM weekly_metrics
                 WHERE couple_id=%s
                   AND (%s::date IS NULL OR week_start >= %s)
                   AND (%s::date IS NULL OR week_start <= %s)
                 ORDER BY week_start
                """,
                (couple_id, start, start, end, end),
            )
            return list(await cur.fetchall())

    async def get_report(self, couple_id: UUID, week_start: date) -> dict[str, Any] | None:
        async with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT week_start, status, report, execution_trace, updated_at
                  FROM reports WHERE couple_id=%s AND week_start=%s
                """,
                (couple_id, week_start),
            )
            return await cur.fetchone()

    async def get_couple_lexicon(self, couple_id: UUID) -> dict[str, tuple[str, str]]:
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT term, canonical, polarity FROM couple_lexicon WHERE couple_id=%s",
                    (couple_id,),
                )
            ).fetchall()
            return {term: (canonical, polarity) for term, canonical, polarity in rows}

    async def apply_upload(
        self,
        couple_id: UUID,
        *,
        user_id: UUID,
        base_hashes: set[str],
        kakao_names: dict[str, str],
        new_messages: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        weeks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """메시지→세션→지표→잡을 단일 트랜잭션으로 반영한다."""
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, couple_id)
            couple_row = await (
                await conn.execute(
                    """
                    UPDATE couples SET kakao_name_a=%s, kakao_name_b=%s
                     WHERE couple_id=%s AND status='active' AND (user_a=%s OR user_b=%s)
                     RETURNING couple_id
                    """,
                    (kakao_names["a"], kakao_names["b"], couple_id, user_id, user_id),
                )
            ).fetchone()
            if not couple_row:
                raise RepositoryError(
                    "COUPLE_NOT_ACTIVE", "활성 커플만 업로드할 수 있습니다"
                )

            current_hash_rows = await (
                await conn.execute(
                    "SELECT msg_hash FROM messages WHERE couple_id=%s", (couple_id,)
                )
            ).fetchall()
            if {row[0] for row in current_hash_rows} != base_hashes:
                # 읽기·CPU 계산 사이 다른 인스턴스가 업로드를 완료했다. 오래된 계산으로
                # 지표를 덮지 않고 클라이언트가 최신 DB 기준으로 재시도하게 한다.
                raise RepositoryError(
                    "UPLOAD_RETRY", "다른 업로드가 먼저 완료되어 재시도가 필요합니다"
                )
            async with conn.cursor() as cur:
                if new_messages:
                    await cur.executemany(
                        """
                        INSERT INTO messages
                            (couple_id, sender, sent_at, body_enc, body_len, is_question, msg_hash)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (couple_id, msg_hash) DO NOTHING
                        """,
                        [
                            (
                                couple_id,
                                m["sender"],
                                m["sent_at"],
                                m["body_enc"],
                                m["body_len"],
                                m["is_question"],
                                m["msg_hash"],
                            )
                            for m in new_messages
                        ],
                    )

                # FK의 ON DELETE SET NULL(session_id) 후 결정론적 세션을 다시 구성한다.
                await cur.execute(
                    "DELETE FROM sessions WHERE couple_id=%s", (couple_id,)
                )
                if sessions:
                    await cur.executemany(
                        """
                        INSERT INTO sessions
                            (couple_id, session_id, started_at, ended_at, initiator, msg_count)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        """,
                        [
                            (
                                couple_id,
                                s["session_id"],
                                s["started_at"],
                                s["ended_at"],
                                s["initiator"],
                                s["msg_count"],
                            )
                            for s in sessions
                        ],
                    )
                    await cur.executemany(
                        """
                        UPDATE messages SET session_id=%s
                         WHERE couple_id=%s AND sent_at >= %s AND sent_at <= %s
                        """,
                        [
                            (s["session_id"], couple_id, s["started_at"], s["ended_at"])
                            for s in sessions
                        ],
                    )

                old_rows = await (
                    await conn.execute(
                        "SELECT week_start, summary_hash FROM weekly_metrics WHERE couple_id=%s",
                        (couple_id,),
                    )
                ).fetchall()
                old_hashes = {row[0]: row[1] for row in old_rows}
                changed = [
                    w["week_start"]
                    for w in weeks
                    if old_hashes.get(w["week_start"]) != w["summary_hash"]
                ]

                if weeks:
                    await cur.executemany(
                        """
                        INSERT INTO weekly_metrics (couple_id, week_start, summary, summary_hash, outliers)
                        VALUES (%s,%s,%s,%s,%s)
                        ON CONFLICT (couple_id, week_start) DO UPDATE SET
                            summary=excluded.summary, summary_hash=excluded.summary_hash,
                            outliers=excluded.outliers, updated_at=now()
                        """,
                        [
                            (
                                couple_id,
                                w["week_start"],
                                Jsonb(w["summary"]),
                                w["summary_hash"],
                                Jsonb(w["outliers"]),
                            )
                            for w in weeks
                        ],
                    )

                await cur.execute(
                    "DELETE FROM weekly_terms WHERE couple_id=%s", (couple_id,)
                )
                term_rows = [term for week in weeks for term in week["terms"]]
                if term_rows:
                    await cur.executemany(
                        """
                        INSERT INTO weekly_terms
                            (couple_id, week_start, sender, canonical, polarity, count)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        """,
                        [
                            (
                                couple_id,
                                t["week_start"],
                                t["sender"],
                                t["canonical"],
                                t["polarity"],
                                t["count"],
                            )
                            for t in term_rows
                        ],
                    )
                await cur.execute(
                    "DELETE FROM term_count_cache WHERE couple_id=%s", (couple_id,)
                )

                if changed:
                    await cur.executemany(
                        """
                        INSERT INTO reports (couple_id, week_start, status)
                        VALUES (%s,%s,'pending')
                        ON CONFLICT (couple_id, week_start) DO UPDATE SET
                            status='pending', report=NULL, execution_trace=NULL, updated_at=now()
                        """,
                        [(couple_id, week_start) for week_start in changed],
                    )

                embed_total = len(sessions) if new_messages else 0
                report_total = len(changed)
                await cur.execute(
                    """
                    INSERT INTO jobs (couple_id, kind, status, total)
                    VALUES (%s,'embed_sessions',%s,%s) RETURNING job_id
                    """,
                    (couple_id, "queued" if embed_total else "done", embed_total),
                )
                embed_job_id = (await cur.fetchone())[0]
                await cur.execute(
                    """
                    INSERT INTO jobs (couple_id, kind, status, total)
                    VALUES (%s,'report_backfill',%s,%s) RETURNING job_id
                    """,
                    (couple_id, "queued" if report_total else "done", report_total),
                )
                report_job_id = (await cur.fetchone())[0]

            return {
                "embed_job_id": embed_job_id,
                "report_job_id": report_job_id,
                "changed_weeks": changed,
            }
