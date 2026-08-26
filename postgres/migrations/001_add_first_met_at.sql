-- Safe, repeatable migration for existing Postgres volumes.
BEGIN;

ALTER TABLE couples
    ADD COLUMN IF NOT EXISTS first_met_at DATE;

COMMIT;
