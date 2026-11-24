"""DB positions / overrides for components on drawing sheets.

Revision ID: f8b9c0d1e2f3
Revises: e6f7a8b9c0d1
"""

from alembic import op
import sqlalchemy as sa

revision = "f8b9c0d1e2f3"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component_map_positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("sheet_id", sa.String(length=121), nullable=False),
        sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["component_id"], ["structural_components.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("component_id", "sheet_id"),
    )
    op.create_index(
        "ix_component_map_positions_project_id",
        "component_map_positions",
        ["project_id"],
    )
    op.create_index(
        "ix_component_map_positions_component_id",
        "component_map_positions",
        ["component_id"],
    )
    op.create_index(
        "ix_component_map_positions_sheet_id",
        "component_map_positions",
        ["sheet_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_component_map_positions_sheet_id", table_name="component_map_positions"
    )
    op.drop_index(
        "ix_component_map_positions_component_id", table_name="component_map_positions"
    )
    op.drop_index(
        "ix_component_map_positions_project_id", table_name="component_map_positions"
    )
    op.drop_table("component_map_positions")
