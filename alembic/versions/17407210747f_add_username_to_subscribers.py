"""add username to subscribers

Revision ID: 17407210747f
Revises: 53a4abc460db
Create Date: 2025-06-19 23:32:31.381844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17407210747f'
down_revision: Union[str, None] = '53a4abc460db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscribers', sa.Column('username', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('subscribers', 'username')
