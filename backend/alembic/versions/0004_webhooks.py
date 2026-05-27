"""Create webhook_endpoints table.

Revision ID: 0004_webhooks
Revises: 0003_schema_cleanup
Create Date: 2026-05-25

Adds the webhook_endpoints table used by the outbound webhook dispatch system.
All statements use IF NOT EXISTS guards so they are safe to re-run.
"""

from alembic import op

revision = "0004_webhooks"
down_revision = "0003_schema_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_endpoints (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
            url         TEXT NOT NULL,
            events      VARCHAR(500) NOT NULL DEFAULT 'push.completed,push.failed',
            secret      TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            failure_count  INTEGER NOT NULL DEFAULT 0,
            last_fired_at  TIMESTAMP WITH TIME ZONE,
            last_failure_at TIMESTAMP WITH TIME ZONE,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_customer_id "
        "ON webhook_endpoints(customer_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_is_active "
        "ON webhook_endpoints(is_active)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_webhook_endpoints_is_active")
    op.execute("DROP INDEX IF EXISTS idx_webhook_endpoints_customer_id")
    op.execute("DROP TABLE IF EXISTS webhook_endpoints")
