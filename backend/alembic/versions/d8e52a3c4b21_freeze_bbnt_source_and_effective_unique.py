"""freeze issued BBNT source data and enforce one effective revision

Revision ID: d8e52a3c4b21
Revises: c7d41f2b9a10
Create Date: 2026-11-11 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e52a3c4b21"
down_revision: Union[str, Sequence[str], None] = "c7d41f2b9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "acceptance_records",
        sa.Column("request_snapshot_json", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_ea_document_project_key_effective",
        "engineering_ai_documents",
        ["project_id", "document_key"],
        unique=True,
        sqlite_where=sa.text("is_effective = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ea_document_project_key_effective",
        table_name="engineering_ai_documents",
    )
    op.drop_column("acceptance_records", "request_snapshot_json")
