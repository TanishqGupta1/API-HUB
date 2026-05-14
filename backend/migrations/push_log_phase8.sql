-- Phase 8: Integration Gateway schema migration (reference only — app uses create_all)
-- Applied automatically on backend startup via Base.metadata.create_all
--
-- If running against an existing DB that has the old VPCE columns, run the
-- DROP statements first, then the ADD statements below.

-- ── Drop old VPCE columns (only needed if upgrading from the first Task 1 attempt) ──
ALTER TABLE product_push_log
    DROP COLUMN IF EXISTS preflight_results,
    DROP COLUMN IF EXISTS preview_payload,
    DROP COLUMN IF EXISTS preview_built_at,
    DROP COLUMN IF EXISTS execution_steps,
    DROP COLUMN IF EXISTS input_hash,
    DROP COLUMN IF EXISTS confirm_token_hash,
    DROP COLUMN IF EXISTS confirm_token_consumed_at;

-- ── Drop old VPCE indexes ──
DROP INDEX IF EXISTS idx_push_log_input_hash;
DROP INDEX IF EXISTS uq_push_log_in_flight;

-- ── Add Integration Gateway columns ──
ALTER TABLE product_push_log
    ADD COLUMN IF NOT EXISTS request_id         UUID UNIQUE DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS key_id             VARCHAR(64),
    ADD COLUMN IF NOT EXISTS idempotency_key    VARCHAR(128),
    ADD COLUMN IF NOT EXISTS payload_hash       VARCHAR(64),
    ADD COLUMN IF NOT EXISTS supplier_slug      VARCHAR(64),
    ADD COLUMN IF NOT EXISTS supplier_sku       VARCHAR(255),
    ADD COLUMN IF NOT EXISTS callback_url       TEXT,
    ADD COLUMN IF NOT EXISTS callback_status    VARCHAR(32) DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS callback_attempts  INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS step_results       JSONB,
    ADD COLUMN IF NOT EXISTS cleanup_targets    JSONB,
    ADD COLUMN IF NOT EXISTS dry_run            BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS retry_of           UUID;

-- ── Widen status column for new vocab ──
ALTER TABLE product_push_log
    ALTER COLUMN status TYPE VARCHAR(50);

-- ── New indexes ──
CREATE INDEX IF NOT EXISTS idx_push_log_payload_hash
    ON product_push_log (payload_hash);

CREATE INDEX IF NOT EXISTS idx_push_log_idempotency
    ON product_push_log (key_id, idempotency_key);

-- Concurrency guard: one active push per (customer, product)
CREATE UNIQUE INDEX IF NOT EXISTS uq_push_log_in_flight
    ON product_push_log (customer_id, product_id)
    WHERE status = 'processing';

-- ── integration_keys table ──
CREATE TABLE IF NOT EXISTS integration_keys (
    id                      VARCHAR(64) PRIMARY KEY,
    key_hash                VARCHAR(128) NOT NULL,
    name                    VARCHAR(255) NOT NULL,
    allowed_customer_ids    JSONB,
    allowed_supplier_slugs  JSONB,
    rate_limit_per_minute   INT DEFAULT 60,
    is_active               BOOLEAN DEFAULT TRUE,
    last_used_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    revoked_at              TIMESTAMPTZ
);
