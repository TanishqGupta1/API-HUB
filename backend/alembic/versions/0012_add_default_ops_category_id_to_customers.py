"""Add default_ops_category_id to customers.

Revision ID: 0012_add_default_ops_category_id
Revises: 0011_add_part_id
Create Date: 2026-06-08

Fallback OPS category per customer — used by _build_setProduct_step when a
product has no storefront-config category override. Without it products land
in OPS with category_id=0 and are hidden from the admin browse view.
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_add_default_ops_category_id"
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
