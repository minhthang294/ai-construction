#!/usr/bin/env python3
"""Create one construction batch ("Đợt thi công") per live Cầu chính segment.

The 17 Bunke pile codes are already Cầu chính PD2 components and are already in
the existing PD2 batch, together with the two Bunke beams. This script never
adds, moves or duplicates Bunke components: it only creates the missing PD1 and
PD3 batches from their Cầu chính segment components and reuses PD2. The Bunke
membership is printed as a check.

Preview is read-only. ``--commit`` creates missing batches, adds missing
segment components, and writes the same audit actions as ``batch_router``.
Reruns are idempotent.

Examples:
  python scripts/create_segment_batches.py \
    --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)"

  # add --commit to write
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.component_models import (  # noqa: E402
    ConstructionBatch,
    ConstructionBatchComponent,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
CAU_CHINH = "cầu chính"
BUNKE = "bunke"
PD2_SEGMENT = 2
BUNKE_PILE_CODES = (
    "A152", "A153", "A154", "A155",
    "B152", "B153", "B154", "B155",
    "D152", "D153", "D156", "D157",
    "E152", "E153", "E154", "E155", "E156",
)
BUNKE_BEAM_CODES = ("A-B-153", "B-D-153")


def fold(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def norm_code(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().upper()


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def live_cau_chinh_segments(
    manifests: Iterable[tuple[str, dict[str, Any]]]
) -> dict[int, set[str]]:
    result: dict[int, set[str]] = defaultdict(set)
    for key, manifest in manifests:
        for sheet in manifest.get("sheets", []):
            zone = fold(sheet.get("zone"))
            segment = sheet.get("segment")
            if zone == CAU_CHINH and isinstance(segment, int):
                result[segment].add(key)
            for marker in sheet.get("markers", []):
                if fold(marker.get("zone")) == CAU_CHINH and isinstance(
                    marker.get("segment"), int
                ):
                    result[marker["segment"]].add(key)
    return {segment: keys for segment, keys in sorted(result.items())}


def batch_name(segment: int) -> str:
    return f"PD{segment} Cầu chính"


def load_manifests(
    maps_root: Path, project_id: str
) -> list[tuple[str, dict[str, Any]]]:
    manifests = []
    if not maps_root.is_dir():
        return manifests
    for folder in sorted(maps_root.iterdir()):
        if not folder.is_dir() or folder.name == "expansion":
            continue
        path = folder / "manifest.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("project_id") == project_id:
            manifests.append((folder.name, data))
    return manifests


def load_components(db: Session, project_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        select(StructuralComponent, StructureZone.name, Segment.number)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(StructuralComponent.project_id == project_id)
        .order_by(StructureZone.name, Segment.number, StructuralComponent.type,
                  StructuralComponent.canonical_code)
    ).all()
    return [
        {
            "id": component.id,
            "code": component.canonical_code,
            "type": component.type,
            "zone": zone,
            "segment": segment,
        }
        for component, zone, segment in rows
    ]


def segment_components(
    components: Iterable[dict[str, Any]], segment: int
) -> list[dict[str, Any]]:
    """Only Cầu chính segment rows; Bunke zone rows are never added."""
    return [
        item
        for item in components
        if fold(item["zone"]) == CAU_CHINH and item["segment"] == segment
    ]


def bunke_membership(
    components: Iterable[dict[str, Any]], batch_ids: set[str]
) -> dict[str, Any]:
    """Check the existing PD2 batch without changing it."""
    components = list(components)
    pd2_piles = {
        norm_code(item["code"]): item["id"]
        for item in components
        if fold(item["zone"]) == CAU_CHINH
        and item["segment"] == PD2_SEGMENT
        and fold(item["type"]) == "pile"
    }
    bunke_beams = {
        norm_code(item["code"]): item["id"]
        for item in components
        if fold(item["zone"]) == BUNKE and fold(item["type"]) == "beam"
    }
    missing_piles = [
        code for code in BUNKE_PILE_CODES
        if code not in pd2_piles or pd2_piles[code] not in batch_ids
    ]
    missing_beams = [
        code for code in BUNKE_BEAM_CODES
        if code not in bunke_beams or bunke_beams[code] not in batch_ids
    ]
    return {
        "piles_present": len(BUNKE_PILE_CODES) - len(missing_piles),
        "piles_total": len(BUNKE_PILE_CODES),
        "missing_piles": missing_piles,
        "beams_present": len(BUNKE_BEAM_CODES) - len(missing_beams),
        "beams_total": len(BUNKE_BEAM_CODES),
        "missing_beams": missing_beams,
    }


def _pick_actor(db: Session, project_id: str, actor_name: str | None) -> User:
    if actor_name:
        actor = db.scalar(
            select(User).where(
                (User.username == actor_name) | (User.id == actor_name)
            )
        )
    else:
        actor = db.scalar(
            select(User)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.role.desc())
        )
    if actor is None:
        raise SystemExit(
            "No project user found; pass --actor <username|id> or create a member first"
        )
    return actor


def _note(segment: int) -> str:
    if segment == PD2_SEGMENT:
        return "Gồm cấu kiện PD2 Cầu chính và cấu kiện Bunke thi công cùng đợt."
    return f"Gồm cấu kiện PD{segment} Cầu chính."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.maps_root.is_dir():
        print(f"Drawing map root not found: {args.maps_root}", file=sys.stderr)
        return 2

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        actor = _pick_actor(db, project.id, args.actor)
        manifests = load_manifests(args.maps_root, project.id)
        segments = live_cau_chinh_segments(manifests)
        if not segments:
            print("No live Cầu chính drawing map found", file=sys.stderr)
            return 2
        components = load_components(db, project.id)
        batches = list(
            db.scalars(
                select(ConstructionBatch).where(ConstructionBatch.project_id == project.id)
            )
        )
        by_name: dict[str, list[ConstructionBatch]] = defaultdict(list)
        for batch in batches:
            by_name[batch.name].append(batch)

        print("BATCH COMMIT" if args.commit else "BATCH PREVIEW (no writes)")
        print(f"  Live Cầu chính segments: {', '.join(f'PD{n}' for n in segments)}")
        desired_by_segment: dict[int, list[dict[str, Any]]] = {}
        for segment, keys in segments.items():
            name = batch_name(segment)
            existing = by_name.get(name, [])
            if len(existing) > 1:
                print(f"  {name}: multiple batches named {name}; review manually", file=sys.stderr)
                return 1
            batch = existing[0] if existing else None
            desired = segment_components(components, segment)
            desired_by_segment[segment] = desired
            current = set()
            if batch is not None:
                current = set(
                    db.scalars(
                        select(ConstructionBatchComponent.component_id).where(
                            ConstructionBatchComponent.batch_id == batch.id
                        )
                    )
                )
            missing = [item for item in desired if item["id"] not in current]
            extra = current - {item["id"] for item in desired}
            print(
                f"  {name}: {'exists' if batch else 'create'}; "
                f"segment components {len(desired)}; in batch {len(current)}; "
                f"to add {len(missing)}; other existing {len(extra)}"
            )
            print(f"    maps: {', '.join(keys)}")
            if extra and segment == PD2_SEGMENT:
                print("    other existing: the two Bunke beams (kept in PD2)")

        pd2_batch = (by_name.get(batch_name(PD2_SEGMENT)) or [None])[0]
        pd2_ids = set()
        if pd2_batch is not None:
            pd2_ids = set(
                db.scalars(
                    select(ConstructionBatchComponent.component_id).where(
                        ConstructionBatchComponent.batch_id == pd2_batch.id
                    )
                )
            )
        if pd2_batch is not None and pd2_ids:
            status = bunke_membership(components, pd2_ids)
            print(
                f"  Bunke pile codes already in {batch_name(PD2_SEGMENT)} batch: "
                f"{status['piles_present']}/{status['piles_total']} "
                "(existing Cầu chính 2 rows; no Bunke copy added)"
            )
            print(
                f"  Bunke beams already in {batch_name(PD2_SEGMENT)} batch: "
                f"{status['beams_present']}/{status['beams_total']}"
            )
            if status["missing_piles"]:
                print("  Bunke piles not in the PD2 batch (reported, not added): "
                      + ", ".join(status["missing_piles"]))
            if status["missing_beams"]:
                print("  Bunke beams not in the PD2 batch (reported, not added): "
                      + ", ".join(status["missing_beams"]))
        else:
            print("  PD2 Cầu chính batch not found; Bunke membership not verified")
        print("  Bunke components added or moved: 0")

        if not args.commit:
            return 0

        created_batches = 0
        added_links = 0
        for segment in segments:
            name = batch_name(segment)
            batch = by_name.get(name, [None])[0]
            if batch is None:
                batch = ConstructionBatch(
                    project_id=project.id,
                    name=name,
                    note=_note(segment),
                    created_by=actor.id,
                )
                db.add(batch)
                db.flush()
                db.add(
                    AuditLog(
                        project_id=project.id,
                        actor_id=actor.id,
                        action="construction_batch_created",
                        entity="ConstructionBatch",
                        entity_id=batch.id,
                        detail=json.dumps(
                            {"name": batch.name, "note": batch.note}, ensure_ascii=False
                        ),
                    )
                )
                created_batches += 1
            current = set(
                db.scalars(
                    select(ConstructionBatchComponent.component_id).where(
                        ConstructionBatchComponent.batch_id == batch.id
                    )
                )
            )
            for item in desired_by_segment[segment]:
                if item["id"] in current:
                    continue
                reason = f"{name} segment component"
                db.add(
                    ConstructionBatchComponent(
                        batch_id=batch.id,
                        component_id=item["id"],
                        added_by=actor.id,
                        reason=reason,
                    )
                )
                db.add(
                    AuditLog(
                        project_id=project.id,
                        actor_id=actor.id,
                        action="construction_batch_component_added",
                        entity="ConstructionBatchComponent",
                        entity_id=f"{batch.id}:{item['id']}",
                        detail=json.dumps(
                            {
                                "batch_id": batch.id,
                                "component_id": item["id"],
                                "reason": reason,
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                current.add(item["id"])
                added_links += 1
        db.commit()
        print(
            f"  committed: batches created {created_batches}; "
            f"components added {added_links}; audit written; Bunke unchanged"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
