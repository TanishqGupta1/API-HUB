"""Create app_settings table.

Revision ID: 0006_app_settings
Revises: 0005_integration_keys
Create Date: 2026-05-27
"""
from alembic import op

revision = "0006_app_settings"
down_revision = "0005_integration_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key        VARCHAR(64) PRIMARY KEY,
            value      JSON NOT NULL DEFAULT '{}'::json,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
