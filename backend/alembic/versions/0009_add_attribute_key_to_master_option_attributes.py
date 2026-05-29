"""add attribute_key to master_option_attributes

Revision ID: 0009_add_attribute_key
Revises: 0008_phase8_pricing
Create Date: 2026-05-26

The attribute_key field is returned by OPS GraphQL (getMasterOptions) and
is needed by the frontend's humanizeAttributeName helper to produce friendly
labels. Previously the value was only stored in raw_json but never surfaced
as a dedicated column, so the page always fell back to raw title strings.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_attribute_key"
down_revision: Union[str, None] = "0008_phase8_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "master_option_attributes",
        sa.Column("attribute_key", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("master_option_attributes", "attribute_key")
