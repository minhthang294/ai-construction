"""store reviewed page extraction enrichment

Revision ID: e2f6a1c9d430
Revises: d8e52a3c4b21
Create Date: 2026-11-11 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f6a1c9d430"
down_revision: Union[str, Sequence[str], None] = "d8e52a3c4b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_ai_page_extractions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_sha256", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extraction_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("verified_by", sa.String(length=36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verify_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "page_id", "model", "prompt_version", "mode",
            name="uq_ea_page_extraction_version",
        ),
    )
    op.create_index(
        op.f("ix_engineering_ai_page_extractions_project_id"),
        "engineering_ai_page_extractions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engineering_ai_page_extractions_document_id"),
        "engineering_ai_page_extractions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engineering_ai_page_extractions_page_id"),
        "engineering_ai_page_extractions",
        ["page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_engineering_ai_page_extractions_status"),
        "engineering_ai_page_extractions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_engineering_ai_page_extractions_status"),
        table_name="engineering_ai_page_extractions",
    )
    op.drop_index(
        op.f("ix_engineering_ai_page_extractions_page_id"),
        table_name="engineering_ai_page_extractions",
    )
    op.drop_index(
        op.f("ix_engineering_ai_page_extractions_document_id"),
        table_name="engineering_ai_page_extractions",
    )
    op.drop_index(
        op.f("ix_engineering_ai_page_extractions_project_id"),
        table_name="engineering_ai_page_extractions",
    )
    op.drop_table("engineering_ai_page_extractions")
