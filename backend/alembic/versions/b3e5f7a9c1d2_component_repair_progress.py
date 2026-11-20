"""component repair scope review and construction progress

Revision ID: b3e5f7a9c1d2
Revises: 170f7a3596cf
Create Date: 2026-11-18 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3e5f7a9c1d2'
down_revision: Union[str, Sequence[str], None] = '170f7a3596cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add construction stages, append-only progress and site bulk idempotency."""
    op.create_table('component_stage_definitions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('component_type', sa.String(length=12), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'component_type', 'code')
    )
    op.create_table('component_stages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('component_id', sa.String(length=36), nullable=False),
    sa.Column('stage_definition_id', sa.String(length=36), nullable=False),
    sa.Column('repair_scope_id', sa.String(length=36), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['component_id'], ['structural_components.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['repair_scope_id'], ['component_repair_scopes.id'], ),
    sa.ForeignKeyConstraint(['stage_definition_id'], ['component_stage_definitions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('component_id', 'stage_definition_id', 'repair_scope_id')
    )
    op.create_index('ix_component_stages_component_id', 'component_stages', ['component_id'])
    op.create_index('ix_component_stages_repair_scope_id', 'component_stages', ['repair_scope_id'])
    op.create_index('ix_component_stages_stage_definition_id', 'component_stages', ['stage_definition_id'])
    # Shared with the site bulk progress wrapper; construction only, no acceptance state.
    op.create_table('component_progress_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('component_id', sa.String(length=36), nullable=False),
    sa.Column('component_stage_id', sa.String(length=36), nullable=False),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('unit', sa.String(length=30), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('evidence_refs', sa.Text(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['component_id'], ['structural_components.id'], ),
    sa.ForeignKeyConstraint(['component_stage_id'], ['component_stages.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_component_progress_events_component_id', 'component_progress_events', ['component_id'])
    op.create_index('ix_component_progress_events_component_stage_id', 'component_progress_events', ['component_stage_id'])
    op.create_index('ix_component_progress_events_event_date', 'component_progress_events', ['event_date'])
    op.create_table('component_progress_batches',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('idempotency_key', sa.String(length=120), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('result_json', sa.Text(), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'idempotency_key', name='uq_progress_batch_project_key')
    )
    op.create_index('ix_component_progress_batches_project_id', 'component_progress_batches', ['project_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_component_progress_batches_project_id', table_name='component_progress_batches')
    op.drop_table('component_progress_batches')
    op.drop_index('ix_component_progress_events_event_date', table_name='component_progress_events')
    op.drop_index('ix_component_progress_events_component_stage_id', table_name='component_progress_events')
    op.drop_index('ix_component_progress_events_component_id', table_name='component_progress_events')
    op.drop_table('component_progress_events')
    op.drop_index('ix_component_stages_stage_definition_id', table_name='component_stages')
    op.drop_index('ix_component_stages_repair_scope_id', table_name='component_stages')
    op.drop_index('ix_component_stages_component_id', table_name='component_stages')
    op.drop_table('component_stages')
    op.drop_table('component_stage_definitions')
