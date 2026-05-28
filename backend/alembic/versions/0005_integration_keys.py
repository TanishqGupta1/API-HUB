"""Create integration_keys table.

Revision ID: 0005_integration_keys
Revises: 0004_webhooks
Create Date: 2026-05-27
"""
from alembic import op

revision = "0005_integration_keys"
down_revision = "0004_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_keys (
            id                     VARCHAR(64) PRIMARY KEY,
            key_hash               VARCHAR(128) NOT NULL,
            name                   VARCHAR(255) NOT NULL,
            allowed_customer_ids   JSONB,
            allowed_supplier_slugs JSONB,
            rate_limit_per_minute  INTEGER NOT NULL DEFAULT 60,
            is_active              BOOLEAN NOT NULL DEFAULT TRUE,
            is_synthetic           BOOLEAN NOT NULL DEFAULT FALSE,
            last_used_at           TIMESTAMP WITH TIME ZONE,
            created_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            revoked_at             TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_integration_keys_key_hash "
        "ON integration_keys(key_hash)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_integration_keys_key_hash")
    op.execute("DROP TABLE IF EXISTS integration_keys")
