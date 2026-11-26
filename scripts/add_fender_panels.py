#!/usr/bin/env python3
"""Add the three Tấm tựa tàu fender panels from the reviewed workbook.

Preview is read-only. ``--commit`` creates the ``Tấm tựa tàu`` design group,
three ``type=beam`` components (K-111-112, K-135-136, K-1), their workbook
stages/quantities and DRAFT positions for the two panels visible on the live
PD3 sheet. K-1 has a detail drawing but no plan label; it is left unplaced and
reported.

Idempotent per component, stage and (component, sheet). Examples:

  python scripts/add_fender_panels.py --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)"

  # add --commit to write
"""

from __future__ import annotations

import argparse
import hashlib
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
    ComponentAlias,
    ComponentMapPosition,
    ComponentStage,
    DesignGroup,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

DEFAULT_WORKBOOK = (
    ROOT / "data" / "storage" / "design-review" / "DAP-danh-muc-va-khoi-luong-ban-ve.xlsx"
)
DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
SHEET_NAME = "Tấm tựa tàu"
GROUP_NAME = "Tấm tựa tàu"
GROUP_DRAWING = "TK-109-113"
ZONE = "Cầu chính"
SEGMENT = 3
PANELS = ("K-111-112", "K-135-136", "K-1")
# Two points on the hatched panel / panel axis, read from live TK-33 (pd3.jpg).
POSITIONS: Dict[str, dict] = {
    "K-111-112": {
        "sheet": "cau-chinh-pd3-plan",
        "points": [[0.3275, 0.29697], [0.35875, 0.29697]],
        "note": (
            "TK-33 tr.39; nhãn K-111-112 + Tấm tựa tàu; điểm đọc trực quan "
            "trên vùng gạch, cần xác nhận."
        ),
    },
    "K-135-136": {
        "sheet": "cau-chinh-pd3-plan",
        "points": [[0.85375, 0.28182], [0.85375, 0.35758]],
        "note": (
            "TK-33 tr.39; nhãn K-135-136 + Tấm tựa tàu; điểm đọc trực quan "
            "trên vùng gạch, cần xác nhận."
        ),
    },
}


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def _number(value) -> Optional[float]:
    if value is None or str(value).strip() in ("", "-"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _rows(workbook: Path) -> Dict[str, List[dict]]:
    wb = load_workbook(workbook, data_only=True, read_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(f"sheet not found: {SHEET_NAME}")
        ws = wb[SHEET_NAME]
        result: Dict[str, List[dict]] = {code: [] for code in PANELS}
        for row in ws.iter_rows(min_row=2, values_only=True):
            page, drawing, group, title_code, quantity_code, source_row, unit, work_item, quantity_raw, review = row
            code = str(title_code or "").strip()
            if code not in result:
                continue
            result[code].append(
                {
                    "page": int(page) if page is not None else None,
                    "drawing": str(drawing or "").strip(),
                    "group": str(group or "").strip(),
                    "title_code": code,
                    "quantity_code": str(quantity_code or "").strip(),
                    "source_row": int(source_row) if source_row is not None else None,
                    "unit": str(unit or "").strip(),
                    "name": str(work_item or "").strip(),
                    "quantity": _number(quantity_raw),
                    "review": str(review or "").strip(),
                }
            )
        for code, items in result.items():
            items.sort(key=lambda item: item["source_row"] or 0)
            if not items:
                raise ValueError(f"no workbook rows for {code}")
            if [item["source_row"] for item in items] != list(range(1, len(items) + 1)):
                raise ValueError(f"{code}: source rows are not 1..{len(items)}")
        if len(result["K-111-112"]) != 30 or len(result["K-135-136"]) != 30:
            raise ValueError("K-111-112/K-135-136 must have 30 rows each")
        if len(result["K-1"]) != 5:
            raise ValueError("K-1 must have 5 rows")
        return result
    finally:
        wb.close()


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


def _segment(db: Session, project_id: str) -> Segment:
    segment = db.scalar(
        select(Segment)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(
            StructureZone.project_id == project_id,
            StructureZone.name == ZONE,
            Segment.number == SEGMENT,
        )
    )
    if segment is None:
        raise SystemExit(f"Segment {ZONE} {SEGMENT} not found")
    return segment


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
        source="DAP-danh-muc-va-khoi-luong-ban-ve.xlsx / Tấm tựa tàu",
        source_page=116,
    )
    db.add(group)
    db.flush()
    return group.id, True


def _definitions(
    db: Session, project_id: str, rows: Dict[str, List[dict]], *, commit: bool
) -> Tuple[Dict[Tuple[str, int], str], int]:
    """Definition key = (prefix, workbook position); shared 1..30 + K1 1..5."""
    result: Dict[Tuple[str, int], str] = {}
    seen = set()
    created = 0
    for code in PANELS:
        prefix = "DAP-TAM-K1" if code == "K-1" else "DAP-TAM"
        for item in rows[code]:
            position = int(item["source_row"])
            key = (prefix, position)
            if key in seen:
                continue
            seen.add(key)
            stage_code = f"{prefix}-{position:02d}"
            existing = db.scalar(
                select(StageDefinition).where(
                    StageDefinition.project_id == project_id,
                    StageDefinition.component_type == "beam",
                    StageDefinition.code == stage_code,
                )
            )
            if existing is not None:
                result[key] = existing.id
                continue
            if not commit:
                created += 1
                continue
            definition = StageDefinition(
                project_id=project_id,
                component_type="beam",
                code=stage_code,
                name=item["name"],
                position=position,
            )
            db.add(definition)
            db.flush()
            result[key] = definition.id
            created += 1
    return result, created


def _scope(db: Session, component: StructuralComponent, reference: str, *, commit: bool) -> Optional[str]:
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
        approval_reference=reference,
    )
    db.add(scope)
    db.flush()
    return scope.id


def _stage_exists(db: Session, component_id: str, definition_id: str, scope_id: str) -> bool:
    return db.scalar(
        select(ComponentStage.id).where(
            ComponentStage.component_id == component_id,
            ComponentStage.stage_definition_id == definition_id,
            ComponentStage.repair_scope_id == scope_id,
        )
    ) is not None


def _position_exists(db: Session, component_id: str, sheet_id: str) -> bool:
    return db.scalar(
        select(ComponentMapPosition.id).where(
            ComponentMapPosition.component_id == component_id,
            ComponentMapPosition.sheet_id == sheet_id,
        )
    ) is not None


def _live_sheet(maps_root: Path, project_id: str, public_id: str) -> Optional[Path]:
    folder_name, _, sheet_id = public_id.rpartition("-")
    folder = maps_root / folder_name
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        return None
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("project_id") != project_id:
        return None
    for sheet in data.get("sheets", []):
        if sheet.get("id") == sheet_id:
            image = folder / str(sheet.get("image") or "")
            return image if image.is_file() else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.workbook.is_file():
        print(f"Workbook not found: {args.workbook}", file=sys.stderr)
        return 2
    try:
        rows = _rows(args.workbook)
    except (OSError, ValueError) as exc:
        print(f"Invalid workbook: {exc}", file=sys.stderr)
        return 2
    source_hash = hashlib.sha256(args.workbook.read_bytes()).hexdigest()

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        actor = _actor(db, project, args.actor)
        segment = _segment(db, project.id)
        group_id, group_created = _group(db, project.id, commit=args.commit)
        definitions, definitions_created = _definitions(
            db, project.id, rows, commit=args.commit
        )

        components_created = 0
        components_existing = 0
        stages_added = 0
        stages_existing = 0
        positions_added = 0
        positions_existing = 0
        problems: List[str] = []
        for code in PANELS:
            items = rows[code]
            component = db.scalar(
                select(StructuralComponent).where(
                    StructuralComponent.project_id == project.id,
                    StructuralComponent.segment_id == segment.id,
                    StructuralComponent.type == "beam",
                    StructuralComponent.canonical_code == code,
                )
            )
            if component is None:
                components_created += 1
                if not args.commit:
                    # Preview: count stages and positions against the future row.
                    stages_added += len(items)
                    if code in POSITIONS:
                        positions_added += 1
                    else:
                        problems.append(
                            f"{code}: no plan label found; detail only, left unplaced"
                        )
                    continue
                component = StructuralComponent(
                    project_id=project.id,
                    segment_id=segment.id,
                    design_group_id=group_id,
                    type="beam",
                    raw_code=code,
                    canonical_code=code,
                    source_id=args.workbook.name,
                    source_hash=source_hash,
                    source_row=items[0]["source_row"],
                    verification="NEEDS_REVIEW",
                    record_origin="MANUAL_ENTRY",
                    created_by=actor.id,
                )
                db.add(component)
                db.flush()
            else:
                components_existing += 1
                if group_id is not None and component.design_group_id != group_id:
                    if args.commit:
                        component.design_group_id = group_id
            if args.commit:
                alias = db.scalar(
                    select(ComponentAlias).where(
                        ComponentAlias.project_id == project.id,
                        ComponentAlias.segment_id == segment.id,
                        ComponentAlias.type == "beam",
                        ComponentAlias.alias == code,
                    )
                )
                if alias is None:
                    db.add(
                        ComponentAlias(
                            project_id=project.id,
                            segment_id=segment.id,
                            type="beam",
                            alias=code,
                            component_id=component.id,
                        )
                    )
            reference = (
                f"{items[0]['drawing']} tr.{items[0]['page']}; "
                f"{args.workbook.name} / {SHEET_NAME} dòng {items[0]['source_row']}"
            )
            if code == "K-1":
                reference += "; chưa thấy nhãn K-1 trên mặt bằng, tạm gán PD3"
            scope_id = _scope(db, component, reference, commit=args.commit)
            prefix = "DAP-TAM-K1" if code == "K-1" else "DAP-TAM"
            for item in items:
                definition_id = definitions.get((prefix, int(item["source_row"])))
                if definition_id is None or scope_id is None:
                    stages_added += 1
                    continue
                if _stage_exists(db, component.id, definition_id, scope_id):
                    stages_existing += 1
                    continue
                stages_added += 1
                if args.commit:
                    note = item["review"] or None
                    if code == "K-111-112" and item["review"]:
                        note = (
                            f"{item['review']}: cột khối lượng ghi "
                            f"{item['quantity_code']}; dùng mã tiêu đề bảng {code}."
                        )
                    db.add(
                        ComponentStage(
                            component_id=component.id,
                            stage_definition_id=definition_id,
                            repair_scope_id=scope_id,
                            design_quantity={
                                "quantity": item["quantity"],
                                "unit": item["unit"],
                                "scope": "COMPONENT",
                                "scope_label": None,
                                "drawing": item["drawing"],
                                "page": str(item["page"]) if item["page"] else None,
                                "note": note,
                            },
                            created_by=actor.id,
                        )
                    )

            placement = POSITIONS.get(code)
            if placement is None:
                problems.append(f"{code}: no plan label found; detail only, left unplaced")
                continue
            if _live_sheet(args.maps_root, project.id, placement["sheet"]) is None:
                problems.append(f"{code}: live sheet {placement['sheet']} not found")
                continue
            if _position_exists(db, component.id, placement["sheet"]):
                positions_existing += 1
                continue
            positions_added += 1
            if args.commit:
                db.add(
                    ComponentMapPosition(
                        project_id=project.id,
                        component_id=component.id,
                        sheet_id=placement["sheet"],
                        points=placement["points"],
                        status="DRAFT",
                        source="ai_extracted",
                        created_by=actor.id,
                        note=placement["note"],
                    )
                )

        if not args.commit:
            print("FENDER PANEL PREVIEW (no writes)")
            print(
                f"  components to create: {components_created}; existing: {components_existing}"
            )
            print(f"  design group to create: {int(group_created)}")
            print(f"  stage definitions to create: {definitions_created}")
            print(f"  stages to add: {stages_added}; existing: {stages_existing}")
            print(f"  positions to add: {positions_added}; existing: {positions_existing}")
            for code in PANELS:
                print(
                    f"    {code}: {len(rows[code])} rows "
                    f"({rows[code][0]['drawing']} tr.{rows[code][0]['page']})"
                )
            if problems:
                print(f"  unresolved/problems: {len(problems)}")
                for problem in problems:
                    print(f"    {problem}")
            return 0

        detail = {
            "workbook": str(args.workbook),
            "components_created": components_created,
            "components_existing": components_existing,
            "group_created": group_created,
            "definitions_created": definitions_created,
            "stages_added": stages_added,
            "stages_existing": stages_existing,
            "positions_added": positions_added,
            "positions_existing": positions_existing,
            "problems": problems,
        }
        db.add(
            AuditLog(
                project_id=project.id,
                actor_id=actor.id,
                action="component_fender_panels_setup",
                entity="ComponentStage",
                entity_id=str(uuid.uuid4()),
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )
        db.commit()
        print("FENDER PANELS COMMITTED")
        print(
            json.dumps(
                {
                    "components_created": components_created,
                    "components_existing": components_existing,
                    "group_created": group_created,
                    "definitions_created": definitions_created,
                    "stages_added": stages_added,
                    "stages_existing": stages_existing,
                    "positions_added": positions_added,
                    "positions_existing": positions_existing,
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
