"""add_missing_composite_indexes

Revision ID: 0bf0948203b6
Revises: 8ac84689a8a2
Create Date: 2026-07-20 08:52:59.394302+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bf0948203b6'
down_revision: Union[str, None] = '8ac84689a8a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # models.py 中定义但 migration 遗漏的复合索引
    op.create_index('ix_pipelines_status_started_at', 'pipelines', ['status', 'started_at'])
    op.create_index('ix_pipeline_steps_pipeline_step', 'pipeline_steps', ['pipeline_id', 'step_id'], unique=True)
    op.create_index('ix_pipeline_steps_status', 'pipeline_steps', ['status'])
    op.create_index('ix_artifacts_pipeline_id', 'artifacts', ['pipeline_id'])


def downgrade() -> None:
    op.drop_index('ix_artifacts_pipeline_id', table_name='artifacts')
    op.drop_index('ix_pipeline_steps_status', table_name='pipeline_steps')
    op.drop_index('ix_pipeline_steps_pipeline_step', table_name='pipeline_steps')
    op.drop_index('ix_pipelines_status_started_at', table_name='pipelines')
