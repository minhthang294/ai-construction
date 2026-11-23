"""Per-component reviewed design parameters.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component_design_parameters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("source_drawing", sa.String(length=120), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_file_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["component_id"], ["structural_components.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("component_id", "name"),
    )
    op.create_index(
        "ix_component_design_parameters_project_id",
        "component_design_parameters",
        ["project_id"],
    )
    op.create_index(
        "ix_component_design_parameters_component_id",
        "component_design_parameters",
        ["component_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_component_design_parameters_component_id",
        table_name="component_design_parameters",
    )
    op.drop_index(
        "ix_component_design_parameters_project_id",
        table_name="component_design_parameters",
    )
    op.drop_table("component_design_parameters")
