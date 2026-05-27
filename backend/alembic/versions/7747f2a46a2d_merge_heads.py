"""merge_heads

Revision ID: 7747f2a46a2d
Revises: 0002_add_attribute_key, 0005_alerting
Create Date: 2026-05-27 12:20:05.442472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7747f2a46a2d'
down_revision: Union[str, None] = ('0002_add_attribute_key', '0005_alerting')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
