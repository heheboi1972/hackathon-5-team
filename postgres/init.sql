-- 역할: DB 초기 스키마 — users/couples/messages/sessions/weekly_metrics/reports/notes/events/pokes + jobs (참조: PRD §6.1, TRD §4.1)
-- 본문은 body_enc(Fernet)로만 저장. 지표 계산은 body_len/is_question 으로 복호화 없이 (TRD §4.1)

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ---------------------------------------------------------------- 사용자·커플
CREATE TABLE users (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(20)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 상태 전이: pending(코드 발급) → awaiting_confirm(B 입력) → active(A 수락) → dissolved (API_SPEC §2)
CREATE TABLE couples (
    couple_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a            UUID NOT NULL REFERENCES users(user_id),
    user_b            UUID REFERENCES users(user_id),
    status            VARCHAR(20) NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','awaiting_confirm','active','dissolved')),
    invite_code       VARCHAR(8) UNIQUE,             -- 영대문자+숫자 8자
    invite_expires_at TIMESTAMPTZ,                   -- 7일 만료
    kakao_name_a      VARCHAR(100),                  -- 카톡 이름 → a/b 매핑 (FR-002)
    kakao_name_b      VARCHAR(100),
    started_at        DATE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- 대화 원본·세션
CREATE TABLE sessions (
    session_id BIGSERIAL PRIMARY KEY,
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at   TIMESTAMPTZ NOT NULL,
    initiator  CHAR(1) NOT NULL CHECK (initiator IN ('a','b')),
    msg_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_sessions_couple_time ON sessions (couple_id, started_at);

CREATE TABLE messages (
    message_id  BIGSERIAL PRIMARY KEY,
    couple_id   UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    session_id  BIGINT REFERENCES sessions(session_id) ON DELETE SET NULL,
    sender      CHAR(1) NOT NULL CHECK (sender IN ('a','b')),
    sent_at     TIMESTAMPTZ NOT NULL,
    body_enc    BYTEA NOT NULL,                      -- Fernet 암호화 본문
    body_len    INTEGER NOT NULL,                    -- 저장 시 계산 (복호화 없이 지표)
    is_question BOOLEAN NOT NULL DEFAULT FALSE,
    msg_hash    VARCHAR(64) NOT NULL,                -- 중복 제거용 (sha256)
    UNIQUE (couple_id, msg_hash)
);
CREATE INDEX idx_messages_couple_time ON messages (couple_id, sent_at);

-- ---------------------------------------------------------------- 지표·리포트
CREATE TABLE weekly_metrics (
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,                        -- 월요일
    summary    JSONB NOT NULL,                       -- API_SPEC §4.1 summary
    outliers   JSONB NOT NULL DEFAULT '[]',          -- moments 후보
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, week_start)
);

CREATE TABLE reports (
    couple_id       UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','generated','insufficient_baseline','failed')),
    report          JSONB,                           -- API_SPEC §4.2 전체 JSON
    execution_trace JSONB,                           -- 에이전트 실행 기록 (NFR-005)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, week_start)
);

-- ---------------------------------------------------------------- 메모·이벤트·콕 찌르기
CREATE TABLE notes (
    note_id     BIGSERIAL PRIMARY KEY,
    couple_id   UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    author      UUID NOT NULL REFERENCES users(user_id),
    range_start TIMESTAMPTZ NOT NULL,
    range_end   TIMESTAMPTZ NOT NULL,
    body        VARCHAR(500) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (range_end >= range_start)
);
CREATE INDEX idx_notes_couple_range ON notes (couple_id, range_start);

CREATE TABLE events (
    event_id   BIGSERIAL PRIMARY KEY,
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    at         DATE NOT NULL,
    kind       VARCHAR(30) NOT NULL,
    label      VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 로드맵 Lv.2 (TRD §10) — 스키마만 선반영
CREATE TABLE pokes (
    poke_id    BIGSERIAL PRIMARY KEY,
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    from_user  UUID NOT NULL REFERENCES users(user_id),
    kind       VARCHAR(30) NOT NULL DEFAULT 'poke',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- 작업 큐 (TRD §4.1)
CREATE TABLE jobs (
    job_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    kind         VARCHAR(30) NOT NULL,          -- report_backfill | report_single
    status       VARCHAR(20) NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','done','failed')),
    total        INTEGER NOT NULL DEFAULT 0,
    done         INTEGER NOT NULL DEFAULT 0,
    failed       INTEGER NOT NULL DEFAULT 0,
    current_week DATE,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_couple ON jobs (couple_id, created_at DESC);
