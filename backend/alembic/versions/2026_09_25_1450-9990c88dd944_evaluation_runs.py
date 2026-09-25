"""evaluation_runs

Revision ID: 9990c88dd944
Revises: 8880c75bb733
Create Date: 2026-09-25 14:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9990c88dd944'
down_revision: Union[str, None] = '8880c75bb733'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evaluation_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('dataset_size', sa.Integer(), nullable=False),
        sa.Column('mean_precision_at_k', sa.Float(), nullable=False),
        sa.Column('mean_recall_at_k', sa.Float(), nullable=False),
        sa.Column('mean_mrr', sa.Float(), nullable=False),
        sa.Column('mean_faithfulness', sa.Float(), nullable=False),
        sa.Column('mean_answer_relevance', sa.Float(), nullable=False),
        sa.Column('results_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_runs_id'), 'evaluation_runs', ['id'], unique=False)
    op.create_index(op.f('ix_evaluation_runs_organization_id'), 'evaluation_runs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_evaluation_runs_user_id'), 'evaluation_runs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evaluation_runs_user_id'), table_name='evaluation_runs')
    op.drop_index(op.f('ix_evaluation_runs_organization_id'), table_name='evaluation_runs')
    op.drop_index(op.f('ix_evaluation_runs_id'), table_name='evaluation_runs')
    op.drop_table('evaluation_runs')
