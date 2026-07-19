"""add kb_configs table for dynamic kb configuration

Revision ID: 8ac84689a8a2
Revises: 24d34db69863
Create Date: 2026-07-19 15:28:53.572195+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ac84689a8a2'
down_revision: Union[str, None] = '24d34db69863'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'kb_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('provider_type', sa.String(32), nullable=False, server_default='obsidian_api'),
        sa.Column('connection_url', sa.String(512), nullable=True),
        sa.Column('auth_token', sa.String(512), nullable=True),
        sa.Column('vault_path', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index('ix_kb_configs_active', 'kb_configs', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_kb_configs_active', table_name='kb_configs')
    op.drop_table('kb_configs')
