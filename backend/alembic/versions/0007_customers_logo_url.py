"""Add customers.logo_url column.

Revision ID: 0007_customers_logo_url
Revises: 0006_app_settings
Create Date: 2026-05-27
"""
from alembic import op

revision = "0007_customers_logo_url"
down_revision = "0006_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS logo_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS logo_url")
