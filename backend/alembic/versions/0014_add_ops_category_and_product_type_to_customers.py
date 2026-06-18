"""Add ops_associated_category_ids and ops_predefined_product_type to customers.

Revision ID: 0014_add_ops_category_and_product_type
Revises: 0013_add_ops_filename
Create Date: 2026-06-16

ops_associated_category_ids: comma-separated OPS category IDs for the
ProductInput.multiple_category field — products pushed for this customer
appear under all listed categories in addition to the default one.

ops_predefined_product_type: controls which OPS section the product lands in.
0 = Print Products (default), 1 = Ready to Buy. Maps to
ProductInput.predefined_product_type and drives product_type selection in
the payload builder.
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_customer_ops_fields"
down_revision = "0013_add_ops_filename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS guards against running on a DB that already had these columns
    # added manually before this migration was written.
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS "
        "ops_associated_category_ids VARCHAR(512)"
    )
    op.execute(
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS "
        "ops_predefined_product_type INTEGER"
    )


def downgrade() -> None:
    op.drop_column("customers", "ops_predefined_product_type")
    op.drop_column("customers", "ops_associated_category_ids")
