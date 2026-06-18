"""Create ops_category_mappings table.

Revision ID: 0015_ops_category_mappings
Revises: 0014_customer_ops_fields
Create Date: 2026-06-18

Maps a Hub product-category name → an auto-created OPS category id, per
customer. Written by _resolve_ops_category in the push gateway on first use;
read back on subsequent pushes so the same category is reused.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0015_ops_category_mappings"
down_revision = "0014_customer_ops_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ops_category_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("category_key", sa.String(150), nullable=False),
        sa.Column("category_name", sa.String(255), nullable=False),
        sa.Column("ops_category_id", sa.Integer, nullable=False),
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_ops_category_customer_key",
        "ops_category_mappings",
        ["customer_id", "category_key"],
    )


def downgrade() -> None:
    op.drop_table("ops_category_mappings")
