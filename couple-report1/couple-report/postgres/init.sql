CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS couples (
    couple_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a UUID NOT NULL REFERENCES users(user_id),
    user_b UUID REFERENCES users(user_id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'awaiting_confirm', 'active', 'dissolved')),
    invite_code CHAR(8) NOT NULL UNIQUE,
    invite_expires_at TIMESTAMPTZ NOT NULL,
    kakao_name_a TEXT,
    kakao_name_b TEXT,
    started_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS couples_active_user_a_idx ON couples(user_a)
WHERE status <> 'dissolved';
CREATE UNIQUE INDEX IF NOT EXISTS couples_active_user_b_idx ON couples(user_b)
WHERE user_b IS NOT NULL AND status <> 'dissolved';

CREATE TABLE IF NOT EXISTS sessions (
    session_id BIGINT PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    initiator CHAR(1) NOT NULL CHECK (initiator IN ('a', 'b')),
    msg_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (couple_id, session_id)
);

CREATE TABLE IF NOT EXISTS messages (
    message_id BIGSERIAL PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    session_id BIGINT REFERENCES sessions(session_id) ON DELETE CASCADE,
    sender CHAR(1) NOT NULL CHECK (sender IN ('a', 'b')),
    sent_at TIMESTAMPTZ NOT NULL,
    body_encrypted TEXT NOT NULL,
    body_hash CHAR(64) NOT NULL,
    msg_type TEXT NOT NULL DEFAULT 'text',
    is_question BOOLEAN NOT NULL DEFAULT false,
    body_len INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (couple_id, body_hash)
);
CREATE INDEX IF NOT EXISTS messages_couple_sent_idx ON messages(couple_id, sent_at);

CREATE TABLE IF NOT EXISTS weekly_metrics (
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    summary JSONB NOT NULL,
    metrics JSONB NOT NULL,
    outliers JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary_hash CHAR(64) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, week_start)
);

CREATE TABLE IF NOT EXISTS reports (
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('generated', 'insufficient_baseline', 'pending', 'failed')),
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary_hash CHAR(64),
    generated_at TIMESTAMPTZ,
    PRIMARY KEY (couple_id, week_start)
);

CREATE TABLE IF NOT EXISTS notes (
    note_id BIGSERIAL PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    author_user_id UUID NOT NULL REFERENCES users(user_id),
    range_start TIMESTAMPTZ NOT NULL,
    range_end TIMESTAMPTZ NOT NULL,
    body VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (range_end >= range_start)
);

CREATE TABLE IF NOT EXISTS events (
    event_id BIGSERIAL PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    event_at TIMESTAMPTZ NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS pokes (
    poke_id BIGSERIAL PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    sender_user_id UUID NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    couple_id UUID REFERENCES couples(couple_id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('embed_sessions', 'build_lexicon', 'report_backfill', 'report_single')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    progress_total INTEGER NOT NULL DEFAULT 0,
    progress_done INTEGER NOT NULL DEFAULT 0,
    progress_failed INTEGER NOT NULL DEFAULT 0,
    current_week DATE,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs(status, created_at);

CREATE TABLE IF NOT EXISTS weekly_terms (
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    sender CHAR(1) NOT NULL CHECK (sender IN ('a', 'b')),
    canonical TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('pos', 'neg', 'neutral')),
    count INTEGER NOT NULL,
    PRIMARY KEY (couple_id, week_start, sender, canonical)
);

CREATE TABLE IF NOT EXISTS couple_lexicon (
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    surface TEXT NOT NULL,
    canonical TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('pos', 'neg', 'neutral', 'exclude')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (couple_id, surface)
);

CREATE TABLE IF NOT EXISTS term_count_cache (
    cache_id BIGSERIAL PRIMARY KEY,
    couple_id UUID NOT NULL REFERENCES couples(couple_id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    range_start TIMESTAMPTZ,
    range_end TIMESTAMPTZ,
    result JSONB NOT NULL,
    source_version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS term_count_cache_lookup_idx
ON term_count_cache (
    couple_id,
    term,
    COALESCE(range_start, '-infinity'::timestamptz),
    COALESCE(range_end, 'infinity'::timestamptz)
);

