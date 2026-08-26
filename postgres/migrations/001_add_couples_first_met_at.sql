-- Existing PostgreSQL volumes do not rerun postgres/init.sql after deploys.
-- This migration is idempotent and safe to apply more than once.
ALTER TABLE couples
    ADD COLUMN IF NOT EXISTS first_met_at DATE;
