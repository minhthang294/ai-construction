"""Construction batches and voidable progress events.

Revision ID: a1b2c3d4e5f6
Revises: 639cdb146bf2
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "639cdb146bf2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "construction_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_construction_batches_project_id", "construction_batches", ["project_id"]
    )

    op.create_table(
        "construction_batch_components",
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("added_by", sa.String(length=36), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["construction_batches.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["structural_components.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("batch_id", "component_id"),
    )

    op.add_column(
        "component_progress_events",
        sa.Column("batch_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "component_progress_events",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "component_progress_events",
        sa.Column("voided_by", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "component_progress_events", sa.Column("void_reason", sa.Text(), nullable=True)
    )
    op.create_index(
        "ix_component_progress_events_batch_id",
        "component_progress_events",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_component_progress_events_batch_id",
        table_name="component_progress_events",
    )
    op.drop_column("component_progress_events", "void_reason")
    op.drop_column("component_progress_events", "voided_by")
    op.drop_column("component_progress_events", "voided_at")
    op.drop_column("component_progress_events", "batch_id")
    op.drop_table("construction_batch_components")
    op.drop_index("ix_construction_batches_project_id", table_name="construction_batches")
    op.drop_table("construction_batches")
