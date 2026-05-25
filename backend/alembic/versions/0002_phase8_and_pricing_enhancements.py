"""Phase 8 push-log columns, pricing rule enhancements, integration keys.

Revision ID: 0002_phase8_and_pricing_enhancements
Revises: 0001_baseline
Create Date: 2026-05-22

All statements use IF NOT EXISTS / IF EXISTS so they are safe to re-run.
"""

from alembic import op

revision = "0002_phase8_pricing"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Pricing rule enhancements ────────────────────────────────────────────
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS effective_from TIMESTAMPTZ")
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS effective_until TIMESTAMPTZ")
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS markup_amount NUMERIC(10,2)")
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS min_price NUMERIC(10,2)")
    op.execute("ALTER TABLE markup_rules ADD COLUMN IF NOT EXISTS max_price NUMERIC(10,2)")
    # Allow NULL markup_pct when a fixed markup_amount is used instead
    op.execute("ALTER TABLE markup_rules ALTER COLUMN markup_pct DROP NOT NULL")

    # ── Customer logo ────────────────────────────────────────────────────────
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS logo_url TEXT")

    # ── Phase 8 Integration Gateway — product_push_log additions ─────────────
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS request_id UUID")
    op.execute("UPDATE product_push_log SET request_id = gen_random_uuid() WHERE request_id IS NULL")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_push_log_request_id') THEN
                ALTER TABLE product_push_log ADD CONSTRAINT uq_push_log_request_id UNIQUE (request_id);
            END IF;
        END $$
    """)
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS key_id VARCHAR(64)")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128)")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64)")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS supplier_slug VARCHAR(64)")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS supplier_sku VARCHAR(255)")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS callback_url TEXT")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS callback_status VARCHAR(32) NOT NULL DEFAULT 'not_requested'")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS callback_attempts INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS step_results JSONB")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS cleanup_targets JSONB")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS dry_run BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS retry_of UUID")
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_log_payload_hash ON product_push_log(payload_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_log_idempotency ON product_push_log(key_id, idempotency_key)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_push_log_in_flight ON product_push_log(customer_id, product_id) WHERE status = 'processing'")

    # ── Integration Keys table ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_keys (
            id VARCHAR(64) PRIMARY KEY,
            key_hash VARCHAR(128) NOT NULL,
            name VARCHAR(255) NOT NULL,
            allowed_customer_ids JSONB,
            allowed_supplier_slugs JSONB,
            rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
            last_used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ
        )
    """)
    op.execute("ALTER TABLE integration_keys ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_keys")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS retry_of")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS dry_run")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS cleanup_targets")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS step_results")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS callback_attempts")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS callback_status")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS callback_url")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS supplier_sku")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS supplier_slug")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS payload_hash")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS idempotency_key")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS key_id")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS request_id")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS logo_url")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS max_price")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS min_price")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS markup_amount")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS effective_until")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS effective_from")
    op.execute("ALTER TABLE markup_rules DROP COLUMN IF EXISTS is_active")
