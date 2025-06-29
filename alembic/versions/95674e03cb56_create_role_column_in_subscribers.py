"""create role column in subscribers

Revision ID: 95674e03cb56
Revises: 17407210747f
Create Date: 2025-06-29 19:37:13.614143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95674e03cb56'
down_revision: Union[str, None] = '17407210747f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

role_enum_name = 'userrole'
user_role_enum = sa.Enum('admin', 'moderator', 'observer', 'user', name=role_enum_name)


def upgrade() -> None:
    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('subscribers',
                  sa.Column('role', user_role_enum, nullable=False, server_default='user')
                  )


def downgrade() -> None:
    op.drop_column('subscribers', 'role')
    user_role_enum.drop(op.get_bind(), checkfirst=True)
