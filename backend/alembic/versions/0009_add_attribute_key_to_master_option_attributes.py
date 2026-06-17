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
    # IF NOT EXISTS: on a fresh DB, Base.metadata.create_all has already
    # created this column from the model before migrations replay.
    op.execute(
        "ALTER TABLE master_option_attributes "
        "ADD COLUMN IF NOT EXISTS attribute_key VARCHAR(100)"
    )


def downgrade() -> None:
    op.drop_column("master_option_attributes", "attribute_key")
