"""Add username to pending_requests

Revision ID: 53a4abc460db
Revises: b31e4d951d9e
Create Date: 2025-06-18 19:03:13.167330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53a4abc460db'
down_revision: Union[str, None] = 'b31e4d951d9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pending_requests', sa.Column('username', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('pending_requests', 'username')
