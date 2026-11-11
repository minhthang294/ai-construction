"""knowledge base effective revisions and deterministic acceptance foundations

Revision ID: c7d41f2b9a10
Revises: bf490c940488
Create Date: 2026-11-11 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d41f2b9a10"
down_revision: Union[str, Sequence[str], None] = "bf490c940488"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # System A: effective revision and richer ingestion metadata.
    op.add_column("engineering_ai_documents", sa.Column("change_note", sa.Text(), nullable=True))
    op.add_column(
        "engineering_ai_documents",
        sa.Column("is_effective", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "engineering_ai_documents",
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engineering_ai_documents",
        sa.Column("effective_by", sa.String(length=36), nullable=True),
    )
    op.add_column("engineering_ai_document_pages", sa.Column("tables_json", sa.Text(), nullable=True))
    op.add_column(
        "engineering_ai_document_chunks",
        sa.Column("section", sa.String(length=255), nullable=True),
    )

    # System B: deterministic numbering, participant library, reuse/staleness.
    op.create_table(
        "acceptance_number_sequences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("start_number", sa.Integer(), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("reset_policy", sa.String(length=20), nullable=False),
        sa.Column("period_key", sa.String(length=20), nullable=True),
        sa.Column("date_format", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "kind", name="uq_acceptance_number_project_kind"),
    )
    op.create_index(
        op.f("ix_acceptance_number_sequences_project_id"),
        "acceptance_number_sequences",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "acceptance_participant_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=500), nullable=True),
        sa.Column("position", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_acceptance_participant_profiles_project_id"),
        "acceptance_participant_profiles",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acceptance_participant_profiles_role"),
        "acceptance_participant_profiles",
        ["role"],
        unique=False,
    )

    op.add_column(
        "acceptance_requests",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "acceptance_requests",
        sa.Column("requested_by_profile_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "acceptance_requests",
        sa.Column("supervisor_profile_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "acceptance_requests",
        sa.Column("investor_profile_id", sa.String(length=36), nullable=True),
    )

    op.add_column("acceptance_records", sa.Column("number", sa.String(length=40), nullable=True))
    op.add_column(
        "acceptance_records",
        sa.Column("request_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "acceptance_records",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("acceptance_records", sa.Column("supersedes_id", sa.String(length=36), nullable=True))
    with op.batch_alter_table("acceptance_records", recreate="always") as batch:
        batch.drop_constraint("uq_acceptance_record_request", type_="unique")
        batch.create_unique_constraint(
            "uq_acceptance_record_request_revision", ["request_id", "revision"]
        )
    op.create_index(
        "uq_acceptance_record_project_number",
        "acceptance_records",
        ["project_id", "number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_acceptance_record_project_number", table_name="acceptance_records")
    with op.batch_alter_table("acceptance_records", recreate="always") as batch:
        batch.drop_constraint("uq_acceptance_record_request_revision", type_="unique")
        batch.create_unique_constraint("uq_acceptance_record_request", ["request_id"])
    op.drop_column("acceptance_records", "supersedes_id")
    op.drop_column("acceptance_records", "revision")
    op.drop_column("acceptance_records", "request_updated_at")
    op.drop_column("acceptance_records", "number")
    op.drop_column("acceptance_requests", "investor_profile_id")
    op.drop_column("acceptance_requests", "supervisor_profile_id")
    op.drop_column("acceptance_requests", "requested_by_profile_id")
    op.drop_column("acceptance_requests", "revision")
    op.drop_index(op.f("ix_acceptance_participant_profiles_role"), table_name="acceptance_participant_profiles")
    op.drop_index(
        op.f("ix_acceptance_participant_profiles_project_id"),
        table_name="acceptance_participant_profiles",
    )
    op.drop_table("acceptance_participant_profiles")
    op.drop_index(
        op.f("ix_acceptance_number_sequences_project_id"),
        table_name="acceptance_number_sequences",
    )
    op.drop_table("acceptance_number_sequences")
    op.drop_column("engineering_ai_document_chunks", "section")
    op.drop_column("engineering_ai_document_pages", "tables_json")
    op.drop_column("engineering_ai_documents", "effective_by")
    op.drop_column("engineering_ai_documents", "effective_at")
    op.drop_column("engineering_ai_documents", "is_effective")
    op.drop_column("engineering_ai_documents", "change_note")
