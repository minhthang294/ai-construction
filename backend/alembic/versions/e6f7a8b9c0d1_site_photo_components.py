"""Project-scoped component links for site photos.

Revision ID: e6f7a8b9c0d1
Revises: b7c8d9e0f1a2
"""

import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

PREFIX = "@components:"


def _encoded_ids(raw: str | None) -> list[str]:
    if not raw or not raw.startswith(PREFIX):
        return []
    try:
        data = json.loads(raw[len(PREFIX):])
    except (TypeError, ValueError):
        return []
    ids = data.get("ids") if isinstance(data, dict) else None
    return [str(item) for item in ids] if isinstance(ids, list) else []


def upgrade() -> None:
    op.create_table(
        "site_photo_components",
        sa.Column("photo_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["site_photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("photo_id", "component_id"),
    )
    op.create_index(
        "ix_site_photo_components_component_id",
        "site_photo_components",
        ["component_id"],
    )
    op.create_index(
        "ix_site_photo_components_project_id",
        "site_photo_components",
        ["project_id"],
    )

    # Move ids out of the old encoded text; the column becomes caption-only.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, project_id, component FROM site_photos "
            "WHERE component LIKE :prefix"
        ),
        {"prefix": f"{PREFIX}%"},
    ).fetchall()
    now = datetime.now(timezone.utc)
    for photo_id, project_id, raw in rows:
        inserted = 0
        for component_id in _encoded_ids(raw):
            owner = conn.execute(
                sa.text("SELECT project_id FROM structural_components WHERE id = :id"),
                {"id": component_id},
            ).scalar()
            if owner != project_id:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO site_photo_components "
                    "(photo_id, component_id, project_id, created_by, created_at) "
                    "VALUES (:photo_id, :component_id, :project_id, NULL, :created_at)"
                ),
                {
                    "photo_id": photo_id,
                    "component_id": component_id,
                    "project_id": project_id,
                    "created_at": now,
                },
            )
            inserted += 1
        if inserted:
            conn.execute(
                sa.text("UPDATE site_photos SET component = NULL WHERE id = :id"),
                {"id": photo_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT photo_id, project_id, component_id FROM site_photo_components "
            "ORDER BY photo_id, component_id"
        )
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for photo_id, _project_id, component_id in rows:
        grouped.setdefault(photo_id, []).append(component_id)

    for photo_id, component_ids in grouped.items():
        codes = []
        for component_id in component_ids:
            code = conn.execute(
                sa.text("SELECT canonical_code FROM structural_components WHERE id = :id"),
                {"id": component_id},
            ).scalar()
            codes.append(code or component_id)
        caption = conn.execute(
            sa.text("SELECT component FROM site_photos WHERE id = :id"),
            {"id": photo_id},
        ).scalar()
        restored = PREFIX + json.dumps(
            {"ids": component_ids, "label": caption or ", ".join(codes)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        conn.execute(
            sa.text("UPDATE site_photos SET component = :value WHERE id = :id"),
            {"value": restored, "id": photo_id},
        )

    op.drop_index(
        "ix_site_photo_components_project_id", table_name="site_photo_components"
    )
    op.drop_index(
        "ix_site_photo_components_component_id", table_name="site_photo_components"
    )
    op.drop_table("site_photo_components")
