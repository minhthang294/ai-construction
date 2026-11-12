"""add work_name to daily work logs

Revision ID: a7c3e9f2b641
Revises: e2f6a1c9d430
Create Date: 2026-11-12 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3e9f2b641"
down_revision: Union[str, Sequence[str], None] = "e2f6a1c9d430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store the unique catalog work name selected for a daily work log.

    The work-item catalog can contain several rows with the same display name
    (for example one "Đục bỏ bê tông om vỡ" row per pile group).  The report
    keeps the selected name even when no single catalog row is referenced.
    """

    op.add_column(
        "daily_work_logs",
        sa.Column("work_name", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("daily_work_logs", "work_name")
