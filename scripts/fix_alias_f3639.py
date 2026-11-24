"""Fix DM rows 46-50: alias F-36-39 -> I-36-39 and link the imported drafts.

The acceptance workbook names beam ``F-36-39`` in DM rows 46-50, but the
catalog code is ``I-36-39`` (Cầu chính PD1).  This script keeps the raw alias,
adds the component-stage links with the same matcher as the workbook importer,
and leaves PYC/BBNT status untouched (draft).  Preview is the default; pass
``--commit`` to write.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.acceptance.models import (  # noqa: E402
    AcceptanceRecord,
    AcceptanceRequest,
    ComponentAcceptanceLink,
)
from app.core.component_models import ComponentAlias, StructuralComponent  # noqa: E402
from app.core.models import AuditLog, Project  # noqa: E402

IMPORTER_PATH = ROOT / "scripts" / "import_acceptance_workbook.py"
RAW_ALIAS = "F-36-39"
TARGET_CODE = "I-36-39"
TARGET_TYPE = "beam"
SEGMENT = 1
DM_ROWS = (46, 47, 48, 49, 50)
MARKER = "[import_acceptance_workbook]"


def _load_importer():
    spec = importlib.util.spec_from_file_location("acceptance_workbook_importer", IMPORTER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load importer: {IMPORTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request_for_row(db: Session, project_id: str, row: int) -> Optional[AcceptanceRequest]:
    marker = f"{MARKER} sheet=DM; row={row};"
    return db.scalar(
        select(AcceptanceRequest).where(
            AcceptanceRequest.project_id == project_id,
            AcceptanceRequest.notes.contains(marker),
        )
    )


def _draft_record(db: Session, request: AcceptanceRequest) -> Optional[AcceptanceRecord]:
    if request.status != "draft":
        return None
    return db.scalar(
        select(AcceptanceRecord)
        .where(
            AcceptanceRecord.request_id == request.id,
            AcceptanceRecord.status == "draft",
        )
        .order_by(AcceptanceRecord.revision.desc())
    )


def _plan_for(
    importer,
    request: AcceptanceRequest,
    record: AcceptanceRecord,
    row: int,
):
    number = (request.number or "").removeprefix("YC-")
    return importer.RowPlan(
        row=row,
        number=number,
        work=request.subject or "",
        target="",
        location=request.location or "",
        yc_date=request.request_date,
        nt_date=record.record_date,
        nt_formula=False,
        in_segment_hint=True,
    )


def _target_component(context) -> StructuralComponent:
    matches = [
        item
        for item in context.components
        if item.canonical_code == TARGET_CODE and item.type == TARGET_TYPE
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one {TARGET_TYPE} {TARGET_CODE} in Cầu chính PD{SEGMENT}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _alias_state(db: Session, project_id: str, component_id: str) -> Tuple[bool, Optional[ComponentAlias]]:
    aliases = list(
        db.scalars(
            select(ComponentAlias).where(
                ComponentAlias.project_id == project_id,
                ComponentAlias.alias == RAW_ALIAS,
            )
        ).all()
    )
    for alias in aliases:
        if alias.component_id != component_id:
            print(
                f"Alias {RAW_ALIAS} already points to component {alias.component_id}, "
                f"not {component_id}",
                file=sys.stderr,
            )
            raise SystemExit(2)
    return bool(aliases), aliases[0] if aliases else None


def _planned_rows(importer, context, db: Session, project_id: str, component) -> Tuple[dict, List[int]]:
    planned = {}
    missing_rows = []
    for row in DM_ROWS:
        request = _request_for_row(db, project_id, row)
        record = _draft_record(db, request) if request is not None else None
        if request is None or record is None:
            missing_rows.append(row)
            continue
        plan = _plan_for(importer, request, record, row)
        links, stage_missing, _unverified = importer._row_stage_links(
            context, plan, component, []
        )
        if stage_missing:
            planned[row] = {
                "request": request.number,
                "record": record.number,
                "to_add": [],
                "unresolved": "công đoạn chưa khớp",
            }
            continue
        new_links = []
        for component_id, stage_id, scope_id in links:
            exists = db.scalar(
                select(ComponentAcceptanceLink.id).where(
                    ComponentAcceptanceLink.project_id == project_id,
                    ComponentAcceptanceLink.component_id == component_id,
                    ComponentAcceptanceLink.stage_id == stage_id,
                    ComponentAcceptanceLink.scope_id == scope_id,
                    ComponentAcceptanceLink.record_id == record.id,
                )
            )
            if not exists:
                new_links.append((component_id, stage_id, scope_id))
        planned[row] = {
            "request": request.number,
            "record": record.number,
            "to_add": new_links,
            "unresolved": "" if new_links or links else "không khớp công đoạn",
        }
    return planned, missing_rows


def _print_preview(alias_created: bool, planned: dict, missing_rows: List[int]) -> None:
    print("FIX PREVIEW (no writes)")
    print(f"  Alias {RAW_ALIAS} -> {TARGET_CODE}: {'missing' if alias_created else 'exists'}")
    for row in sorted(planned):
        item = planned[row]
        if item["unresolved"]:
            print(f"  Row {row} ({item['request']}): unresolved - {item['unresolved']}")
        else:
            print(f"  Row {row} ({item['request']}): {len(item['to_add'])} link(s) to add")
    if missing_rows:
        print("  Rows without imported draft: " + ", ".join(str(row) for row in missing_rows))


def _commit(
    db: Session,
    context,
    project: Project,
    component: StructuralComponent,
    alias_created: bool,
    planned: dict,
    missing_rows: List[int],
) -> dict:
    added_links = 0
    for row in sorted(planned):
        item = planned[row]
        for component_id, stage_id, scope_id in item["to_add"]:
            db.add(
                ComponentAcceptanceLink(
                    project_id=project.id,
                    component_id=component_id,
                    stage_id=stage_id,
                    scope_id=scope_id,
                    record_id=item["record_id"],
                    created_by=context.actor.id,
                )
            )
            added_links += 1
    detail = {
        "raw_alias": RAW_ALIAS,
        "canonical_code": TARGET_CODE,
        "alias_created": alias_created,
        "links_added": added_links,
        "rows": {
            str(row): {
                "request": item["request"],
                "record": item["record"],
                "links_added": len(item["to_add"]),
                "unresolved": item["unresolved"],
            }
            for row, item in sorted(planned.items())
        },
        "rows_without_draft": missing_rows,
    }
    db.add(
        AuditLog(
            project_id=project.id,
            actor_id=context.actor.id,
            action="acceptance_alias_fix_applied",
            entity="AcceptanceAliasFix",
            entity_id=str(uuid.uuid4()),
            detail=json.dumps(detail, ensure_ascii=False),
        )
    )
    db.commit()
    return {"alias_created": alias_created, "links_added": added_links, "rows": detail["rows"]}


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    importer = _load_importer()
    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        context = importer._load_context(db, project, SEGMENT, {}, None)
        component = _target_component(context)
        alias_exists, _alias = _alias_state(db, project.id, component.id)
        planned, missing_rows = _planned_rows(
            importer, context, db, project.id, component
        )
        # Keep the record id alongside the plan for commit.
        for row, item in planned.items():
            request = _request_for_row(db, project.id, row)
            record = _draft_record(db, request) if request is not None else None
            item["record_id"] = record.id if record is not None else None
            if item["record_id"] is None:
                item["to_add"] = []
                item["unresolved"] = "không có BBNT nháp"

        if not args.commit:
            _print_preview(not alias_exists, planned, missing_rows)
            return 0

        alias_created = False
        if not alias_exists:
            db.add(
                ComponentAlias(
                    project_id=project.id,
                    segment_id=component.segment_id,
                    type=component.type,
                    alias=RAW_ALIAS,
                    component_id=component.id,
                )
            )
            db.flush()
            alias_created = True
        result = _commit(
            db,
            context,
            project,
            component,
            alias_created,
            planned,
            missing_rows,
        )
        print("FIX COMMITTED")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
