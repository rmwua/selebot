"""sync schema

Revision ID: b31e4d951d9e
Revises: 
Create Date: 2025-06-11 19:56:37.996018

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b31e4d951d9e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1) включаем расширения
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2) создаём таблицу celebrities с дополнительными полями
    op.create_table(
        'celebrities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('normalized_name', sa.Text(), nullable=True),
        sa.Column('ascii_name', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('geo', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'category', 'geo', name='uq_celeb_name_cat_geo')
    )
    # GIN-индексы для быстрых LIKE/% и fuzzy (%-оператор)
    op.create_index(
        'idx_celebrities_normalized_name_trgm',
        'celebrities',
        ['normalized_name'],
        postgresql_using='gin',
        postgresql_ops={'normalized_name': 'gin_trgm_ops'}
    )
    op.create_index(
        'idx_celebrities_ascii_name_trgm',
        'celebrities',
        ['ascii_name'],
        postgresql_using='gin',
        postgresql_ops={'ascii_name': 'gin_trgm_ops'}
    )

    # 3) создаём таблицу pending_requests сразу с полем bot_message_id
    op.create_table(
        'pending_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('bot_message_id', sa.Integer(), nullable=True),
        sa.Column('celebrity_name', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('geo', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'subscribers',
        sa.Column('chat_id', sa.BigInteger(), primary_key=True)
    )

def downgrade() -> None:
    # откат в обратном порядке
    op.drop_table('pending_requests')
    op.drop_index('idx_celebrities_ascii_name_trgm',      table_name='celebrities')
    op.drop_index('idx_celebrities_normalized_name_trgm', table_name='celebrities')
    op.drop_table('celebrities')
    op.drop_table('subscribers')
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
