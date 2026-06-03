"""Add part_id column to product_variants.

Revision ID: 0011_add_part_id
Revises: 0010_alerting
Create Date: 2026-06-03

The PromoStandards SanMar adapter and ingest schemas already pass a per-variant
`part_id` (the supplier's uniqueKey for getFilteredInventoryLevels v200), but
there was no DB column to persist it. The inventory-only re-fetch path in
modules/promostandards/adapter.py:191 queries ProductVariant.part_id, which
raised AttributeError at runtime.

This migration adds a nullable VARCHAR(100) with an index so the filtered
inventory lookup can return quickly. Existing rows back-fill as NULL — the
next product sync will populate them.
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_add_part_id"
down_revision = "0010_alerting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("part_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_product_variants_part_id",
        "product_variants",
        ["part_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_variants_part_id", table_name="product_variants")
    op.drop_column("product_variants", "part_id")
