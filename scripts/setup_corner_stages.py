#!/usr/bin/env python3
"""Attach the eight Cầu dẫn corner-beam work items to every Q-xxx component.

Preview is read-only. ``--commit`` creates/uses the ``Góc dầm`` design group,
eight ``component_stage_definitions`` rows and one ``component_stages`` row per
corner per work item. Quantities stay ``null`` because the workbook says
``XEM TỔNG CỘT PHÂN NHÓM``; the group-III total is kept in the JSON note.

Idempotent per (component, stage definition, design scope). Examples:

  python scripts/setup_corner_stages.py --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)"

  # add --commit to write
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.component_models import (  # noqa: E402
    ComponentStage,
    DesignGroup,
    RepairScope,
    StageDefinition,
    StructuralComponent,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

DEFAULT_CORNER_SOURCE = (
    ROOT / "data" / "storage" / "design-review" / "DAP-cau-dan-goc-dam-nhom-III.csv"
)
DEFAULT_WORKBOOK = (
    ROOT / "data" / "storage" / "design-review" / "DAP-danh-muc-va-khoi-luong-ban-ve.xlsx"
)
GROUP_NAME = "Góc dầm"
GROUP_DRAWING = "TK-98"
WORKBOOK_SHEET = "Cầu dẫn công tác dầm"
STAGE_PREFIX = "DAP-GOC"


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def _actor(db: Session, project: Project, actor_name: Optional[str]) -> User:
    if actor_name:
        actor = db.scalar(
            select(User).where((User.username == actor_name) | (User.id == actor_name))
        )
    else:
        actor = db.scalar(
            select(User)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project.id)
            .order_by(ProjectMember.role.desc())
        )
    if actor is None:
        raise SystemExit(
            "No project user found; pass --actor <username|id> or create a member first"
        )
    return actor


def _corner_codes(source: Path) -> List[Tuple[str, int]]:
    """Return (Q-code, CSV row number) in workbook order."""
    import csv

    rows: List[Tuple[str, int]] = []
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle, delimiter=";"), start=2):
            code = str(row.get("location_code") or "").strip().upper()
            if code.startswith("Q-"):
                rows.append((code, index))
    return rows


def _workbook_stages(workbook: Path) -> List[dict]:
    """Read the eight group-III work items (rows 42-49) with units and totals."""
    wb = load_workbook(workbook, data_only=True, read_only=True)
    try:
        if WORKBOOK_SHEET not in wb.sheetnames:
            raise ValueError(f"sheet not found: {WORKBOOK_SHEET}")
        ws = wb[WORKBOOK_SHEET]
        stages: List[dict] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            group = str(row[2] or "").strip()
            source_row = row[3]
            if group != "III" or source_row is None:
                continue
            try:
                position = int(source_row)
            except (TypeError, ValueError):
                continue
            if not 1 <= position <= 8:
                continue
            stages.append(
                {
                    "position": position,
                    "name": str(row[4] or "").strip(),
                    "unit": str(row[5] or "").strip(),
                    "total": _number(row[9]),
                }
            )
        stages.sort(key=lambda item: item["position"])
        if [item["position"] for item in stages] != list(range(1, 9)):
            raise ValueError("workbook group III does not have exactly rows 1-8")
        return stages
    finally:
        wb.close()


def _number(value) -> Optional[float]:
    if value is None or str(value).strip() in ("", "-"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _group(db: Session, project_id: str, *, commit: bool) -> Tuple[Optional[str], bool]:
    existing = db.scalar(
        select(DesignGroup).where(
            DesignGroup.project_id == project_id,
            DesignGroup.group_type == "BEAM_REPAIR_CLASS",
            DesignGroup.name == GROUP_NAME,
            DesignGroup.drawing == GROUP_DRAWING,
        )
    )
    if existing is not None:
        return existing.id, False
    if not commit:
        return None, True
    group = DesignGroup(
        project_id=project_id,
        group_type="BEAM_REPAIR_CLASS",
        name=GROUP_NAME,
        drawing=GROUP_DRAWING,
        source=(
            "DAP-danh-muc-va-khoi-luong-ban-ve.xlsx / "
            "Cầu dẫn góc dầm III + Cầu dẫn công tác dầm (nhóm III)"
        ),
        source_page=104,
    )
    db.add(group)
    db.flush()
    return group.id, True


def _definition(
    db: Session, project_id: str, stage: dict, *, commit: bool
) -> Tuple[Optional[str], bool]:
    code = f"{STAGE_PREFIX}-{stage['position']:02d}"
    existing = db.scalar(
        select(StageDefinition).where(
            StageDefinition.project_id == project_id,
            StageDefinition.component_type == "beam",
            StageDefinition.code == code,
        )
    )
    if existing is not None:
        return existing.id, False
    if not commit:
        return None, True
    definition = StageDefinition(
        project_id=project_id,
        component_type="beam",
        code=code,
        name=stage["name"],
        position=stage["position"],
    )
    db.add(definition)
    db.flush()
    return definition.id, True


def _scope(db: Session, component: StructuralComponent, *, commit: bool) -> Optional[str]:
    existing = db.scalar(
        select(RepairScope)
        .where(
            RepairScope.component_id == component.id,
            RepairScope.kind == "DESIGN_SCOPE",
            RepairScope.revision == 1,
        )
        .order_by(RepairScope.id)
    )
    if existing is not None:
        return existing.id
    if not commit:
        return None
    scope = RepairScope(
        component_id=component.id,
        kind="DESIGN_SCOPE",
        verification="NEEDS_REVIEW",
        revision=1,
        approval_reference=f"{component.source_id} dòng {component.source_row}",
    )
    db.add(scope)
    db.flush()
    return scope.id


def _quantity(stage: dict) -> dict:
    note = "XEM TỔNG CỘT PHÂN NHÓM"
    if stage["total"] is not None:
        note += f"; tổng nhóm III = {stage['total']:g} {stage['unit']}"
    return {
        "quantity": None,
        "unit": stage["unit"],
        "scope": "SUBGROUP",
        "scope_label": "Nhóm III",
        "drawing": "TK-106",
        "page": "112",
        "note": note,
    }


def _stage_exists(db: Session, component_id: str, definition_id: str, scope_id: str) -> bool:
    return db.scalar(
        select(ComponentStage.id).where(
            ComponentStage.component_id == component_id,
            ComponentStage.stage_definition_id == definition_id,
            ComponentStage.repair_scope_id == scope_id,
        )
    ) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--corner-source", type=Path, default=DEFAULT_CORNER_SOURCE)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.corner_source.is_file():
        print(f"Corner source not found: {args.corner_source}", file=sys.stderr)
        return 2
    if not args.workbook.is_file():
        print(f"Workbook not found: {args.workbook}", file=sys.stderr)
        return 2
    try:
        corners = _corner_codes(args.corner_source)
        stages = _workbook_stages(args.workbook)
    except (OSError, ValueError) as exc:
        print(f"Invalid source: {exc}", file=sys.stderr)
        return 2

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        actor = _actor(db, project, args.actor)
        group_id, group_created = _group(db, project.id, commit=args.commit)
        definitions: Dict[int, str] = {}
        definitions_created = 0
        for stage in stages:
            definition_id, created = _definition(db, project.id, stage, commit=args.commit)
            if definition_id is not None:
                definitions[stage["position"]] = definition_id
            definitions_created += int(created)

        problems: List[str] = []
        stages_added = 0
        stages_existing = 0
        components = 0
        for code, source_row in corners:
            component = db.scalar(
                select(StructuralComponent).where(
                    StructuralComponent.project_id == project.id,
                    StructuralComponent.type == "beam",
                    StructuralComponent.canonical_code == code,
                )
            )
            if component is None:
                problems.append(f"{code}: component not found (row {source_row})")
                continue
            components += 1
            if group_id is not None and component.design_group_id != group_id:
                if args.commit:
                    component.design_group_id = group_id
            scope_id = _scope(db, component, commit=args.commit)
            for stage in stages:
                definition_id = definitions.get(stage["position"])
                if definition_id is None:
                    # Preview with a new definition: the row will exist after commit.
                    stages_added += 1
                    continue
                if scope_id is None:
                    stages_added += 1
                    continue
                if _stage_exists(db, component.id, definition_id, scope_id):
                    stages_existing += 1
                    continue
                stages_added += 1
                if args.commit:
                    db.add(
                        ComponentStage(
                            component_id=component.id,
                            stage_definition_id=definition_id,
                            repair_scope_id=scope_id,
                            design_quantity=_quantity(stage),
                            created_by=actor.id,
                        )
                    )

        if not args.commit:
            print("CORNER STAGE PREVIEW (no writes)")
            print(f"  corner rows: {len(corners)}; components found: {components}")
            print(f"  design group to create: {int(group_created)}")
            print(f"  stage definitions to create: {definitions_created}")
            print(f"  stages to add: {stages_added}; existing: {stages_existing}")
            for stage in stages:
                print(
                    f"    {stage['position']}. {stage['name']} [{stage['unit']}] "
                    f"group III total={stage['total']}"
                )
            if problems:
                print(f"  problems: {len(problems)}")
                for problem in problems:
                    print(f"    {problem}")
            return 0

        detail = {
            "corner_source": str(args.corner_source),
            "workbook": str(args.workbook),
            "corner_rows": len(corners),
            "components": components,
            "group_created": group_created,
            "definitions_created": definitions_created,
            "stages_added": stages_added,
            "stages_existing": stages_existing,
            "problems": problems,
        }
        db.add(
            AuditLog(
                project_id=project.id,
                actor_id=actor.id,
                action="component_corner_stages_setup",
                entity="ComponentStage",
                entity_id=str(uuid.uuid4()),
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )
        db.commit()
        print("CORNER STAGES COMMITTED")
        print(
            json.dumps(
                {
                    "components": components,
                    "group_created": group_created,
                    "definitions_created": definitions_created,
                    "stages_added": stages_added,
                    "stages_existing": stages_existing,
                    "problems": problems,
                    "committed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
