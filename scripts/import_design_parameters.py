#!/usr/bin/env python
"""Preview/commit per-pile design parameters from a reviewed CSV export.

Usage:
  python scripts/import_design_parameters.py \
    --database sqlite:///path/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)" \
    --csv path/to/DAP-coc-thong-so-TK19-TK25.csv [--commit]

Preview never writes. `--commit` inserts missing parameters, leaves identical
rows untouched, refuses to overwrite a different stored value, and writes one
audit entry.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _database_url(value: str) -> str:
    if value.startswith("sqlite://") or "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="SQLAlchemy database URL")
    parser.add_argument("--project", required=True, help="Exact project name")
    parser.add_argument("--csv", required=True, help="Reviewed parameter CSV")
    parser.add_argument(
        "--actor",
        default=None,
        help="Username for created_by/audit; defaults to an admin/project_manager",
    )
    parser.add_argument("--commit", action="store_true", help="Write the preview")
    args = parser.parse_args()

    if not os.path.isfile(args.csv):
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 2

    os.environ["DATABASE_URL"] = _database_url(args.database)
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "backend"))

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.design_parameter_import import commit_import, prepare_import
    from app.core.models import Project, ProjectMember, User

    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        actor = None
        if args.actor:
            actor = db.scalar(select(User).where(User.username == args.actor))
        if actor is None:
            actor = db.scalar(select(User).where(User.role == "admin").order_by(User.username))
        if actor is None:
            member = db.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.role.in_(("project_manager", "engineer")),
                )
            )
            actor = db.get(User, member.user_id) if member else None
        if actor is None:
            print("No admin/project member available for created_by/audit", file=sys.stderr)
            return 2

        preview = prepare_import(db, project.id, args.csv)
        print(f"Project: {project.name} ({project.id})")
        print(f"CSV rows: {preview['csv_rows']} · source sha256 {preview['source_file_hash'][:12]}…")
        print(
            "Matched: "
            f"{preview['matched_rows']} rows / {preview['matched_components']} piles "
            f"({preview['components_with_t']} with t)"
        )
        print(f"Parameters planned: {preview['planned_parameters']} · unchanged: {preview['unchanged']}")
        print(f"Unmatched: {len(preview['unmatched'])} · ambiguous: {len(preview['ambiguous'])} "
              f"· conflicts: {len(preview['conflicts'])} · invalid: {len(preview['invalid'])}")
        for item in preview["unmatched"]:
            print(
                f"  unmatched: {item['zone']} / {item['code']} "
                f"({item['drawing']} page {item['page']} row {item['source_row']})"
            )
        for item in preview["ambiguous"]:
            candidates = ", ".join(candidate["id"] for candidate in item["candidates"])
            print(f"  ambiguous: {item['zone']} / {item['code']} -> {candidates}")
        for item in preview["conflicts"]:
            print(f"  conflict: {item['zone']} / {item['code']} · {item['values']}")
        for item in preview["invalid"]:
            print(f"  invalid numeric: {item['zone']} / {item['code']} row {item['source_row']}")
        if not preview["existing_table"]:
            print("Note: component_design_parameters table missing; commit requires migration.")
        if args.commit:
            summary = commit_import(db, preview, actor.id)
            print(f"COMMITTED: {summary}")
        else:
            print("PREVIEW ONLY — no rows written.")
            print(f"  parameters to insert: {len(preview['parameters'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
