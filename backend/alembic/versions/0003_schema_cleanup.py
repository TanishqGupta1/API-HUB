"""Schema cleanup — image mirroring columns.

Revision ID: 0003_schema_cleanup
Revises: 0001_baseline
Create Date: 2026-05-25

Adds mirrored_at + its index to product_images.  All other columns that were
previously in the _SCHEMA_UPGRADES startup list are already captured in
0001_baseline (CREATE TABLE IF NOT EXISTS) and 0002_phase8_pricing.

All statements use IF NOT EXISTS guards so they are safe to re-run.
"""

from alembic import op

revision = "0003_schema_cleanup"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Image mirroring pipeline (Phase 5 Tier 2 #8) ─────────────────────────
    op.execute(
        "ALTER TABLE product_images ADD COLUMN IF NOT EXISTS "
        "mirrored_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_images_mirrored_at "
        "ON product_images(mirrored_at)"
    )

    # ── product_images supplier_url unique constraint ─────────────────────────
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_product_images_supplier_url'
            ) THEN
                ALTER TABLE product_images
                ADD CONSTRAINT uq_product_images_supplier_url
                UNIQUE (product_id, supplier_image_url);
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE product_images "
        "DROP CONSTRAINT IF EXISTS uq_product_images_supplier_url"
    )
    op.execute(
        "DROP INDEX IF EXISTS idx_product_images_mirrored_at"
    )
    op.execute(
        "ALTER TABLE product_images DROP COLUMN IF EXISTS mirrored_at"
    )
