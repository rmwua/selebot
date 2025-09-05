"""add reasons field to celebrities

Revision ID: 8926c928bb1e
Revises: 95674e03cb56
Create Date: 2025-09-05 13:01:20.953854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8926c928bb1e'
down_revision: Union[str, None] = '95674e03cb56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('celebrities', sa.Column('reason', sa.Text, nullable=True))

def downgrade() -> None:
    op.drop_column('celebrities', 'reason')