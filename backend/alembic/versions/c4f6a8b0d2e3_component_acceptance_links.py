"""component acceptance links

Revision ID: c4f6a8b0d2e3
Revises: b3e5f7a9c1d2
Create Date: 2026-11-18 16:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f6a8b0d2e3'
down_revision: Union[str, Sequence[str], None] = 'b3e5f7a9c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add explicit component/stage/scope links to PYC and BBNT (acceptance-owned)."""
    op.create_table('component_acceptance_links',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('component_id', sa.String(length=36), nullable=False),
    sa.Column('stage_id', sa.String(length=36), nullable=True),
    sa.Column('scope_id', sa.String(length=36), nullable=True),
    sa.Column('request_id', sa.String(length=36), nullable=True),
    sa.Column('record_id', sa.String(length=36), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(request_id IS NULL) <> (record_id IS NULL)',
                       name='ck_component_acceptance_link_single_target'),
    sa.ForeignKeyConstraint(['component_id'], ['structural_components.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['record_id'], ['acceptance_records.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['request_id'], ['acceptance_requests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['scope_id'], ['component_repair_scopes.id'], ),
    sa.ForeignKeyConstraint(['stage_id'], ['component_stages.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_component_acceptance_links_project_id', 'component_acceptance_links', ['project_id'])
    op.create_index('ix_component_acceptance_links_component_id', 'component_acceptance_links', ['component_id'])
    op.create_index('ix_component_acceptance_links_stage_id', 'component_acceptance_links', ['stage_id'])
    op.create_index('ix_component_acceptance_links_scope_id', 'component_acceptance_links', ['scope_id'])
    op.create_index('ix_component_acceptance_links_request_id', 'component_acceptance_links', ['request_id'])
    op.create_index('ix_component_acceptance_links_record_id', 'component_acceptance_links', ['record_id'])
    op.create_index(
        'uq_component_acceptance_link',
        'component_acceptance_links',
        ['project_id', 'component_id', sa.text("coalesce(stage_id, '')"),
         sa.text("coalesce(scope_id, '')"), sa.text("coalesce(request_id, '')"),
         sa.text("coalesce(record_id, '')")],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_component_acceptance_link', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_record_id', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_request_id', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_scope_id', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_stage_id', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_component_id', table_name='component_acceptance_links')
    op.drop_index('ix_component_acceptance_links_project_id', table_name='component_acceptance_links')
    op.drop_table('component_acceptance_links')
