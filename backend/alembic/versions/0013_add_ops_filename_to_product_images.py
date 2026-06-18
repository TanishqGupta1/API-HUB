"""Add ops_filename to product_images.

Revision ID: 0013_add_ops_filename
Revises: 0012_add_default_ops_category
Create Date: 2026-06-10

Approach B image support: stores the OPS media filename for a product image
after it has been manually uploaded via the OPS admin UI. The push gateway
uses this value as products_large_image_name in setProductsImageGallery — if
null the image step is skipped (no broken gallery rows in OPS).
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_ops_filename"
down_revision = "0012_add_default_ops_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("ops_filename", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_images", "ops_filename")
