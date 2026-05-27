"""Add alerting tables and alerted idempotency columns.

Revision ID: 0005_alerting
Revises: 0004_webhooks
Create Date: 2026-05-27

Creates the notifications and scheduler_heartbeat tables.
Adds alerted boolean columns to product_push_log and sync_jobs so the
checker never fires duplicate notifications for the same failure.
"""

from alembic import op

revision = "0005_alerting"
down_revision = "0002_add_attribute_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type        VARCHAR(50)  NOT NULL,
            severity    VARCHAR(20)  NOT NULL DEFAULT 'error',
            title       VARCHAR(255) NOT NULL,
            body        TEXT         NOT NULL,
            link        VARCHAR(500),
            is_read     BOOLEAN      NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_heartbeat (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            last_ran_at     TIMESTAMP WITH TIME ZONE,
            interval_hours  INTEGER NOT NULL DEFAULT 1,
            updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "ALTER TABLE product_push_log ADD COLUMN IF NOT EXISTS alerted BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE sync_jobs ADD COLUMN IF NOT EXISTS alerted BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sync_jobs DROP COLUMN IF EXISTS alerted")
    op.execute("ALTER TABLE product_push_log DROP COLUMN IF EXISTS alerted")
    op.execute("DROP TABLE IF EXISTS scheduler_heartbeat")
    op.execute("DROP INDEX IF EXISTS idx_notifications_type")
    op.execute("DROP TABLE IF EXISTS notifications")
