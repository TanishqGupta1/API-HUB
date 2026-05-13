-- Phase 8: push_log schema migration (reference only — app uses create_all)
-- Applied automatically on backend startup via Base.metadata.create_all

ALTER TABLE product_push_log
    ADD COLUMN IF NOT EXISTS preflight_results      JSONB,
    ADD COLUMN IF NOT EXISTS preview_payload        JSONB,
    ADD COLUMN IF NOT EXISTS preview_built_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS execution_steps        JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS cleanup_targets        JSONB,
    ADD COLUMN IF NOT EXISTS dry_run                BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS input_hash             VARCHAR(64),
    ADD COLUMN IF NOT EXISTS confirm_token_hash     VARCHAR(64),
    ADD COLUMN IF NOT EXISTS confirm_token_consumed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_push_log_input_hash
    ON product_push_log (input_hash);

-- Concurrency guard: only one executing push per (customer, product)
CREATE UNIQUE INDEX IF NOT EXISTS uq_push_log_in_flight
    ON product_push_log (customer_id, product_id)
    WHERE status = 'executing';
