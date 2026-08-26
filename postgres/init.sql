-- 역할: DB 초기 스키마 — users/couples/messages/sessions/weekly_metrics/reports/notes/events/pokes + jobs + couple_lexicon/weekly_terms (참조: PRD §6.1, TRD §4.1)
-- 본문은 body_encrypted(Fernet)로만 저장. 지표 계산은 body_len/is_question 으로 복호화 없이 (TRD §4.1)
-- P-5 예외: couple_lexicon / weekly_terms / term_count_cache 는 단어 단위 집계를 평문 저장.
--           원문 복원 불가, 커플 해제 시 CASCADE 삭제. term_count_cache 는 사용자가 실제로 물어본 단어만 남는다.

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
    user_a            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_b            UUID REFERENCES users(user_id) ON DELETE CASCADE,
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
-- session_id = started_at 의 epoch 초 (결정론). 재업로드로 세션을 다시 나눠도 같은 세션은 같은 ID → 리포트 발췌·Qdrant·메모 참조 유지
CREATE TABLE sessions (
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at   TIMESTAMPTZ NOT NULL,
    initiator  CHAR(1) NOT NULL CHECK (initiator IN ('a','b')),   -- 표시용 (지표 아님)
    msg_count  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (couple_id, session_id)
);
CREATE INDEX idx_sessions_couple_time ON sessions (couple_id, started_at);

CREATE TABLE messages (
    message_id  BIGSERIAL PRIMARY KEY,
    couple_id   UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    session_id  BIGINT,
    sender      CHAR(1) NOT NULL CHECK (sender IN ('a','b')),
    sent_at     TIMESTAMPTZ NOT NULL,
    body_encrypted TEXT NOT NULL,                     -- Fernet 암호화 본문 (base64, ASCII-safe)
    body_len    INTEGER NOT NULL,                    -- 저장 시 계산 (복호화 없이 지표)
    is_question BOOLEAN NOT NULL DEFAULT FALSE,
    body_hash   VARCHAR(64) NOT NULL,                -- 중복 제거용 (sha256)
    UNIQUE (couple_id, body_hash),
    -- SET NULL 은 session_id 만 (PG15+). 컬럼을 안 적으면 couple_id 까지 NULL 로 만들어 not-null 위반 (ISSUE C7)
    FOREIGN KEY (couple_id, session_id) REFERENCES sessions(couple_id, session_id) ON DELETE SET NULL (session_id)
);
CREATE INDEX idx_messages_couple_time ON messages (couple_id, sent_at);
CREATE INDEX idx_messages_session     ON messages (couple_id, session_id);   -- 인용·evidence·review 조회
CREATE INDEX idx_couples_user_a ON couples (user_a);                           -- GET /couples/me 가드
CREATE INDEX idx_couples_user_b ON couples (user_b);

-- ---------------------------------------------------------------- 지표·리포트
CREATE TABLE weekly_metrics (
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,                        -- 월요일
    summary    JSONB NOT NULL,                       -- API_SPEC §4.1 summary
    summary_hash VARCHAR(64) NOT NULL,               -- sha256(summary). 바뀐 주차만 리포트 재생성 (API_SPEC §3.1 규칙 8)
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
    author      UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
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
    event_at   TIMESTAMPTZ NOT NULL,
    kind       TEXT NOT NULL,
    payload    JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 로드맵 Lv.2 (TRD §10) — 스키마만 선반영
CREATE TABLE pokes (
    poke_id    BIGSERIAL PRIMARY KEY,
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    from_user  UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind       VARCHAR(30) NOT NULL DEFAULT 'poke',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- 감성 단어 "내 단어" (FR-002 sentiment, P-5 예외)
-- append-only: 한 번 분류된 term 은 재분류하지 않음 (재현성). seed 는 공용 시드 사전, llm 은 build_lexicon 잡
CREATE TABLE couple_lexicon (
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    surface   VARCHAR(50) NOT NULL,
    canonical VARCHAR(50) NOT NULL,                  -- 철자 변형만 묶음 (조아→좋아). 동의어는 분리
    sentiment VARCHAR(8)  NOT NULL CHECK (sentiment IN ('pos','neg','neutral','exclude')),
    source    VARCHAR(8)  NOT NULL DEFAULT 'llm' CHECK (source IN ('seed','llm')),
    PRIMARY KEY (couple_id, surface)
);

-- 주차·사람별 집계 (평문). 양쪽 저장하되 API 응답은 요청자 본인 것만 (P-3 예외)
CREATE TABLE weekly_terms (
    couple_id  UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    sender     CHAR(1) NOT NULL CHECK (sender IN ('a','b')),
    canonical  VARCHAR(50) NOT NULL,
    sentiment  VARCHAR(7) NOT NULL CHECK (sentiment IN ('pos','neg','neutral')),
    count      INTEGER NOT NULL,
    PRIMARY KEY (couple_id, week_start, sender, canonical)
);

-- 챗봇 단어 횟수 검색 캐시 (FR-006 term_count). 질문이 들어온 단어만 채워진다.
-- sender 컬럼을 두지 않는다 = 발화자별 집계가 구조적으로 불가능 (P-3 예외 "내 단어는 본인만" 보호).
-- 값은 요청 시 본문을 메모리에서 복호화해 세고 즉시 폐기한 결과이며, 평문 본문은 디스크에 쓰지 않는다.
CREATE TABLE term_count_cache (
    couple_id   UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    term        VARCHAR(50) NOT NULL,        -- tokenize() 로 정규화된 질의어
    week_start  DATE NOT NULL,
    count       INTEGER NOT NULL,            -- 커플 합산
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, term, week_start)
);

-- ---------------------------------------------------------------- 작업 큐 (TRD §4.1)
CREATE TABLE jobs (
    job_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    couple_id    UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    kind         VARCHAR(30) NOT NULL,          -- embed_sessions | build_lexicon | report_backfill | report_single
    status       VARCHAR(20) NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','done','failed')),
    total        INTEGER NOT NULL DEFAULT 0,
    done         INTEGER NOT NULL DEFAULT 0,
    failed       INTEGER NOT NULL DEFAULT 0,
    current_week DATE,
    payload      JSONB NOT NULL DEFAULT '{}',
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_couple ON jobs (couple_id, created_at DESC);
