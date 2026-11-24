#!/usr/bin/env python3
"""Place owner-approved missing drawing-map markers from a reviewed JSON file.

Preview is read-only. ``--commit`` creates the missing Cầu dẫn corner-beam
catalog rows (manual-entry path, NEEDS_REVIEW) and inserts DRAFT
``component_map_positions`` rows with source ``ai_extracted``. It never edits a
manifest, image, source drawing or the private CSV. Idempotent per
(component, sheet).

Examples:
  python scripts/place_missing_markers.py --database sqlite:///data/app.db \
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
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.component_models import (  # noqa: E402
    ComponentAlias,
    ComponentMapPosition,
    RepairScope,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

DEFAULT_PLACEMENTS = (
    ROOT / "data" / "storage" / "dap-maps" / "expansion" / "placements" / "placements.json"
)
DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
DEFAULT_CORNER_SOURCE = (
    ROOT / "data" / "storage" / "design-review" / "DAP-cau-dan-goc-dam-nhom-III.csv"
)


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def _validate_marker(marker: dict, sheet_id: str) -> None:
    """Reject a marker that cannot be stored as a map position."""
    if not isinstance(marker, dict):
        raise ValueError(f"{sheet_id}: marker is not an object")
    code = str(marker.get("code") or "").strip()
    type_ = str(marker.get("type") or "").strip()
    points = marker.get("points")
    if not code or type_ not in ("pile", "beam"):
        raise ValueError(f"{sheet_id}: invalid code/type {code!r}/{type_!r}")
    if not isinstance(points, list) or not points:
        raise ValueError(f"{sheet_id}/{code}: points are missing")
    if type_ == "pile" and len(points) != 1:
        raise ValueError(f"{sheet_id}/{code}: a pile needs exactly one point")
    if type_ == "beam" and len(points) < 2:
        raise ValueError(f"{sheet_id}/{code}: a beam needs at least two points")
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"{sheet_id}/{code}: invalid point {point!r}")
        for value in point:
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                raise ValueError(f"{sheet_id}/{code}: point outside [0,1]: {point!r}")


def _load_placements(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "dap-placements/v1":
        raise ValueError(f"Unsupported placements schema: {data.get('schema')!r}")
    for sheet_id, sheet in data.get("sheets", {}).items():
        for marker in sheet.get("markers", []):
            _validate_marker(marker, sheet_id)
    return data


def _live_sheets(maps_root: Path, project_id: str) -> Dict[str, dict]:
    """Read live manifests and return public sheet ids -> sheet metadata."""
    result: Dict[str, dict] = {}
    if not maps_root.is_dir():
        return result
    for folder in sorted(maps_root.iterdir()):
        if not folder.is_dir() or folder.name == "expansion" or folder.name.startswith("."):
            continue
        path = folder / "manifest.json"
        if not path.is_file():
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("project_id") != project_id:
            continue
        for sheet in manifest.get("sheets", []):
            image = folder / str(sheet.get("image") or "")
            if not image.is_file():
                continue
            public_id = f"{folder.name}-{sheet.get('id')}"
            result[public_id] = {
                "key": folder.name,
                "sheet": sheet,
                "image": image,
            }
    return result


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


def _segment(db: Session, project_id: str, zone: str, number: int) -> Optional[Segment]:
    return db.scalar(
        select(Segment)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(
            StructureZone.project_id == project_id,
            StructureZone.name == zone,
            Segment.number == number,
        )
    )


def _component(
    db: Session, project_id: str, segment_id: str, type_: str, code: str
) -> Optional[StructuralComponent]:
    component = db.scalar(
        select(StructuralComponent).where(
            StructuralComponent.project_id == project_id,
            StructuralComponent.segment_id == segment_id,
            StructuralComponent.type == type_,
            StructuralComponent.canonical_code == code,
        )
    )
    if component is not None:
        return component
    return db.scalar(
        select(StructuralComponent)
        .join(ComponentAlias, ComponentAlias.component_id == StructuralComponent.id)
        .where(
            ComponentAlias.project_id == project_id,
            ComponentAlias.segment_id == segment_id,
            ComponentAlias.type == type_,
            ComponentAlias.alias == code,
        )
    )


def _ensure_corners(
    db: Session,
    project: Project,
    actor: User,
    corner_catalog: List[dict],
    source: Path,
    *,
    commit: bool,
) -> Tuple[int, int, List[str], Dict[Tuple[str, str, str], Optional[str]]]:
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    source_id = source.name if source.is_file() else None
    created = 0
    existing = 0
    problems: List[str] = []
    planned: Dict[Tuple[str, str, str], Optional[str]] = {}
    for entry in corner_catalog:
        code = str(entry.get("code") or "").strip().upper()
        zone = str(entry.get("zone") or "").strip()
        segment_number = entry.get("segment")
        if not code or not zone or segment_number is None:
            problems.append(f"invalid corner catalog entry: {entry!r}")
            continue
        segment = _segment(db, project.id, zone, int(segment_number))
        if segment is None:
            problems.append(f"{code}: segment {zone} {segment_number} not found")
            continue
        found = _component(db, project.id, segment.id, "beam", code)
        if found is not None:
            existing += 1
            planned[(segment.id, "beam", code)] = found.id
            continue
        if not commit:
            created += 1
            planned[(segment.id, "beam", code)] = None
            continue
        component = StructuralComponent(
            project_id=project.id,
            segment_id=segment.id,
            type="beam",
            raw_code=code,
            canonical_code=code,
            source_id=source_id,
            source_hash=source_hash,
            source_row=entry.get("source_row"),
            verification="NEEDS_REVIEW",
            record_origin="MANUAL_ENTRY",
            created_by=actor.id,
        )
        db.add(component)
        db.flush()
        db.add(
            RepairScope(
                component_id=component.id,
                kind="DESIGN_SCOPE",
                verification="NEEDS_REVIEW",
                revision=1,
                approval_reference=(
                    f"{entry.get('drawing')} tr.{entry.get('page')}; "
                    f"{source.name} dòng {entry.get('source_row')}"
                ),
            )
        )
        db.add(
            ComponentAlias(
                project_id=project.id,
                segment_id=segment.id,
                type="beam",
                alias=code,
                component_id=component.id,
            )
        )
        created += 1
        planned[(segment.id, "beam", code)] = component.id
    return created, existing, problems, planned


def _position_exists(db: Session, component_id: str, sheet_id: str) -> bool:
    return db.scalar(
        select(ComponentMapPosition.id).where(
            ComponentMapPosition.component_id == component_id,
            ComponentMapPosition.sheet_id == sheet_id,
        )
    ) is not None


def _planned_positions(
    db: Session,
    project: Project,
    live_sheets: Dict[str, dict],
    sheets: Dict[str, dict],
    planned_corners: Dict[Tuple[str, str, str], Optional[str]],
    *,
    commit: bool,
    actor: User,
) -> Tuple[List[dict], List[str], int]:
    planned: List[dict] = []
    problems: List[str] = []
    existing = 0
    for sheet_id, sheet in sheets.items():
        if sheet_id not in live_sheets:
            problems.append(f"{sheet_id}: not a live sheet of this project")
            continue
        live = live_sheets[sheet_id]
        zone = str(sheet.get("zone") or live["sheet"].get("zone") or "")
        segment_number = sheet.get("segment", live["sheet"].get("segment"))
        if segment_number is None:
            problems.append(f"{sheet_id}: sheet has no segment")
            continue
        segment = _segment(db, project.id, zone, int(segment_number))
        if segment is None:
            problems.append(f"{sheet_id}: segment {zone} {segment_number} not found")
            continue
        for marker in sheet.get("markers", []):
            code = str(marker["code"]).strip().upper()
            type_ = marker["type"]
            component = _component(db, project.id, segment.id, type_, code)
            component_id = component.id if component is not None else None
            planned_key = (segment.id, type_, code)
            if component_id is None and planned_key in planned_corners:
                component_id = planned_corners[planned_key] or "planned"
            if component_id is None:
                problems.append(f"{sheet_id}/{code}: component not found")
                continue
            if component_id != "planned" and _position_exists(db, component_id, sheet_id):
                existing += 1
                continue
            item = {
                "sheet_id": sheet_id,
                "component_id": component_id,
                "code": code,
                "type": type_,
                "points": [[float(x), float(y)] for x, y in marker["points"]],
                "note": str(marker.get("note") or "")[:2000] or None,
            }
            planned.append(item)
            if commit:
                db.add(
                    ComponentMapPosition(
                        project_id=project.id,
                        component_id=component_id,
                        sheet_id=sheet_id,
                        points=item["points"],
                        status="DRAFT",
                        source="ai_extracted",
                        created_by=actor.id,
                        note=item["note"],
                    )
                )
    return planned, problems, existing


def _print_preview(
    data: dict,
    components_created: int,
    components_existing: int,
    planned: List[dict],
    existing_positions: int,
    problems: List[str],
) -> None:
    unresolved = data.get("unresolved", [])
    print("PLACEMENT PREVIEW (no writes)")
    print(f"  Sheets: {len(data.get('sheets', {}))}; markers: {sum(len(s.get('markers', [])) for s in data.get('sheets', {}).values())}")
    print(f"  components to create: {components_created}; existing: {components_existing}")
    print(f"  positions to add: {len(planned)}; existing: {existing_positions}")
    print(f"  unresolved from source: {len(unresolved)}")
    for item in unresolved[:20]:
        print(f"    {item.get('sheet')}/{item.get('code')}: {item.get('reason')}")
    if problems:
        print(f"  skipped/problem rows: {len(problems)}")
        for problem in problems[:20]:
            print(f"    {problem}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--placements", type=Path, default=DEFAULT_PLACEMENTS)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--corner-source", type=Path, default=DEFAULT_CORNER_SOURCE)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.placements.is_file():
        print(f"Placements not found: {args.placements}", file=sys.stderr)
        return 2
    try:
        data = _load_placements(args.placements)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid placements: {exc}", file=sys.stderr)
        return 2

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        live_sheets = _live_sheets(args.maps_root, project.id)
        actor = _actor(db, project, args.actor)
        components_created, components_existing, corner_problems, planned_corners = _ensure_corners(
            db,
            project,
            actor,
            data.get("corner_catalog", []),
            args.corner_source,
            commit=args.commit,
        )
        planned, problems, existing_positions = _planned_positions(
            db,
            project,
            live_sheets,
            data.get("sheets", {}),
            planned_corners,
            commit=args.commit,
            actor=actor,
        )
        problems = corner_problems + problems
        if not args.commit:
            _print_preview(
                data,
                components_created,
                components_existing,
                planned,
                existing_positions,
                problems,
            )
            return 0

        detail = {
            "placements": str(args.placements),
            "components_created": components_created,
            "components_existing": components_existing,
            "positions_added": len(planned),
            "positions_existing": existing_positions,
            "unresolved": data.get("unresolved", []),
            "problems": problems,
        }
        db.add(
            AuditLog(
                project_id=project.id,
                actor_id=actor.id,
                action="component_map_positions_placed",
                entity="ComponentMapPosition",
                entity_id=str(uuid.uuid4()),
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )
        db.commit()
        print("PLACEMENT COMMITTED")
        print(
            json.dumps(
                {
                    "components_created": components_created,
                    "components_existing": components_existing,
                    "positions_added": len(planned),
                    "positions_existing": existing_positions,
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
