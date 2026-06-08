"""Add default_ops_category_id to customers.

Revision ID: 0012_add_default_ops_category
Revises: 0011_add_part_id
Create Date: 2026-06-08

When the gateway pushes a product it must assign it to an OPS category.
Storing a per-customer default avoids having to look up or hard-code the
category every push. NULL means no default is set — the push falls back to
deriving the category from the product's catalog data.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_add_default_ops_category"
down_revision = "0011_add_part_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("default_ops_category_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "default_ops_category_id")
