#!/usr/bin/env python3
"""Place the PD1 additional-scope (phát sinh) piles and beams on live TK-31.

The live ``cau-chinh-pd1-plan`` sheet is TK-31 PD1 (axes 1-48, rows F-I).
Axis->x and row->y are affine fits from the reviewed manifest markers. Piles
F13...I39 and the eight beams are placed on that sheet; C2/E5/A149/A151 are
placed on the TK-02 annex sheet because rows C/E and axes 149/151 are not on
TK-31. Preview is read-only; ``--commit`` writes DRAFT positions and an audit
entry. Idempotent per (component, sheet). No manifest is edited.

Examples:
  python scripts/place_pd1_additional.py --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from statistics import linear_regression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.component_models import (  # noqa: E402
    ComponentMapPosition,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
PLAN_SHEET = "cau-chinh-pd1-plan"
TK02_SHEET = "cau-chinh-pd1-tk02-pd1"
ROWS = "ABCDEFGHI"
PILE_RE = re.compile(r"^([A-I])(\d{1,3})$")

MAIN_PILES = [
    "F13", "F18", "F24", "F25", "F46",
    "G5", "G17", "G20", "G23", "G44", "G47",
    "H8", "H10", "H17", "H20", "H23", "H29", "H38", "H41", "H44",
    "I21", "I39",
]
BEAMS = [
    "F-16-18", "F-18-19", "F-19-21", "F-19-25", "F-31-33",
    "I-16-18", "I-18-21", "I-19-21",
]
# TK-02 annex crops: pixels in the 4x page render (crop x0=900, y0=600).
TK02_PILES = {
    "C2": (1130, 2000),
    "E5": (1320, 1654),
    "A149": (3000, 2250),
    "A151": (4050, 2250),
}
TK02_CROP = (900, 4700, 600, 2700)


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


def _segment(db: Session, project_id: str) -> Segment:
    segment = db.scalar(
        select(Segment)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(
            StructureZone.project_id == project_id,
            StructureZone.name == "Cầu chính",
            Segment.number == 1,
        )
    )
    if segment is None:
        raise SystemExit("Segment Cầu chính 1 not found")
    return segment


def _calibration(maps_root: Path, project_id: str) -> Tuple[float, float, float, float, int, float, float]:
    manifest = json.loads((maps_root / "cau-chinh-pd1" / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("project_id") != project_id:
        raise SystemExit("cau-chinh-pd1 manifest project mismatch")
    sheet = next((item for item in manifest["sheets"] if item["id"] == "plan"), None)
    if sheet is None:
        raise SystemExit("cau-chinh-pd1-plan not found")
    axes: List[float] = []
    xs: List[float] = []
    row_idx: List[float] = []
    ys: List[float] = []
    for marker in sheet.get("markers", []):
        if marker.get("type") != "pile":
            continue
        match = PILE_RE.fullmatch(str(marker.get("code") or ""))
        if not match:
            continue
        row, axis = match.group(1), int(match.group(2))
        if not 1 <= axis <= 48:
            continue
        x, y = marker["points"][0]
        axes.append(axis)
        xs.append(float(x))
        row_idx.append(ROWS.index(row))
        ys.append(float(y))
    if len(axes) < 6:
        raise SystemExit(f"Need >=6 calibration markers, found {len(axes)}")
    # stdlib least squares: the VM venv has no numpy.
    ax_a, ax_b = linear_regression(axes, xs)
    row_a, row_b = linear_regression(row_idx, ys)
    res_x = max(abs(x - (ax_a * a + ax_b)) for a, x in zip(axes, xs))
    res_y = max(abs(y - (row_a * r + row_b)) for r, y in zip(row_idx, ys))
    return ax_a, ax_b, row_a, row_b, len(axes), res_x, res_y


def _point(axis: float, row: str, ax_a: float, ax_b: float, row_a: float, row_b: float) -> List[float]:
    return [round(ax_a * axis + ax_b, 6), round(row_a * ROWS.index(row) + row_b, 6)]


def _live_image(maps_root: Path, project_id: str, map_name: str, sheet_id: str) -> Optional[Path]:
    folder = maps_root / map_name
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


def _position_exists(db: Session, component_id: str, sheet_id: str) -> bool:
    return db.scalar(
        select(ComponentMapPosition.id).where(
            ComponentMapPosition.component_id == component_id,
            ComponentMapPosition.sheet_id == sheet_id,
        )
    ) is not None


def _overlay(image_path: Path, existing: List[dict], added: List[dict], out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = ImageFont.load_default()
    for marker in existing:
        for x, y in marker["points"]:
            px, py = int(float(x) * width), int(float(y) * height)
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), outline=(0, 90, 200), width=1)
    for marker in added:
        points = [(int(float(x) * width), int(float(y) * height)) for x, y in marker["points"]]
        if marker["type"] == "beam" and len(points) >= 2:
            draw.line(points, fill=(220, 0, 0), width=4)
        for px, py in points:
            draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=(220, 0, 0), width=2)
        draw.text((points[0][0] + 8, points[0][1] - 16), marker["code"], fill=(160, 0, 0), font=font)
    image.save(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        try:
            ax_a, ax_b, row_a, row_b, count, max_x, max_y = _calibration(
                args.maps_root, project.id
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Invalid calibration: {exc}", file=sys.stderr)
            return 2
        actor = _actor(db, project, args.actor)
        segment = _segment(db, project.id)
        plan_image = _live_image(args.maps_root, project.id, "cau-chinh-pd1", "plan")
        tk02_image = _live_image(args.maps_root, project.id, "cau-chinh-pd1", "tk02-pd1")
        if plan_image is None:
            print(f"Live sheet not found: {PLAN_SHEET}", file=sys.stderr)
            return 2
        if tk02_image is None:
            print(f"Live sheet not found: {TK02_SHEET}", file=sys.stderr)
            return 2

        problems: List[str] = []
        added: List[dict] = []
        existing = 0
        for code in MAIN_PILES:
            component = db.scalar(
                select(StructuralComponent).where(
                    StructuralComponent.project_id == project.id,
                    StructuralComponent.segment_id == segment.id,
                    StructuralComponent.type == "pile",
                    StructuralComponent.canonical_code == code,
                )
            )
            if component is None:
                problems.append(f"{code}: component not found")
                continue
            match = PILE_RE.fullmatch(code)
            if not match:
                problems.append(f"{code}: invalid row/axis")
                continue
            row, axis = match.group(1), int(match.group(2))
            if row not in "FGHI" or not 1 <= axis <= 48:
                problems.append(f"{code}: row/axis outside TK-31")
                continue
            if _position_exists(db, component.id, PLAN_SHEET):
                existing += 1
                continue
            point = _point(axis, row, ax_a, ax_b, row_a, row_b)
            added.append(
                {
                    "sheet": PLAN_SHEET,
                    "component_id": component.id,
                    "code": code,
                    "type": "pile",
                    "points": [point],
                    "note": (
                        f"TK-31 tr.37; phát sinh PD1 hàng {row} × trục {axis}; "
                        f"fit affine từ {count} marker đã duyệt; DRAFT."
                    ),
                }
            )

        for code in BEAMS:
            component = db.scalar(
                select(StructuralComponent).where(
                    StructuralComponent.project_id == project.id,
                    StructuralComponent.segment_id == segment.id,
                    StructuralComponent.type == "beam",
                    StructuralComponent.canonical_code == code,
                )
            )
            if component is None:
                problems.append(f"{code}: component not found")
                continue
            match = re.fullmatch(r"([A-I])-(\d{1,3})-(\d{1,3})", code)
            if not match:
                problems.append(f"{code}: invalid beam range")
                continue
            row, start, end = match.group(1), int(match.group(2)), int(match.group(3))
            if row not in "FGHI" or not 1 <= start < end <= 48:
                problems.append(f"{code}: row/axis outside TK-31")
                continue
            if _position_exists(db, component.id, PLAN_SHEET):
                existing += 1
                continue
            points = [
                _point(start, row, ax_a, ax_b, row_a, row_b),
                _point(end, row, ax_a, ax_b, row_a, row_b),
            ]
            added.append(
                {
                    "sheet": PLAN_SHEET,
                    "component_id": component.id,
                    "code": code,
                    "type": "beam",
                    "points": points,
                    "note": (
                        f"TK-31 tr.37; phát sinh PD1 dầm hàng {row} trục {start}-{end}; "
                        f"polyline theo fit affine; DRAFT."
                    ),
                }
            )

        x0, x1, y0, y1 = TK02_CROP
        for code, (px, py) in TK02_PILES.items():
            component = db.scalar(
                select(StructuralComponent).where(
                    StructuralComponent.project_id == project.id,
                    StructuralComponent.segment_id == segment.id,
                    StructuralComponent.type == "pile",
                    StructuralComponent.canonical_code == code,
                )
            )
            if component is None:
                problems.append(f"{code}: component not found")
                continue
            if _position_exists(db, component.id, TK02_SHEET):
                existing += 1
                continue
            point = [round((px - x0) / (x1 - x0), 6), round((py - y0) / (y1 - y0), 6)]
            added.append(
                {
                    "sheet": TK02_SHEET,
                    "component_id": component.id,
                    "code": code,
                    "type": "pile",
                    "points": [point],
                    "note": (
                        f"TK-02 tr.8; phát sinh PD1, ô cọc không nhãn theo lưới "
                        f"hàng/trục; DRAFT."
                    ),
                }
            )

        if not args.commit:
            print("PD1 ADDITIONAL PREVIEW (no writes)")
            print(
                f"  calibration: {count} pile markers; x={ax_a:.9f}*axis+{ax_b:.9f}; "
                f"y={row_a:.9f}*row+{row_b:.9f}"
            )
            print(f"  residuals: max x={max_x:.6f}, max y={max_y:.6f}")
            print(f"  positions to add: {len(added)}; existing: {existing}")
            by_sheet: Dict[str, int] = {}
            for item in added:
                by_sheet[item["sheet"]] = by_sheet.get(item["sheet"], 0) + 1
            for sheet_id, value in sorted(by_sheet.items()):
                print(f"    {sheet_id}: {value}")
            for problem in problems:
                print(f"    {problem}")
            return 0 if not problems else 1

        for item in added:
            db.add(
                ComponentMapPosition(
                    project_id=project.id,
                    component_id=item["component_id"],
                    sheet_id=item["sheet"],
                    points=item["points"],
                    status="DRAFT",
                    source="ai_extracted",
                    created_by=actor.id,
                    note=item["note"],
                )
            )
        detail = {
            "calibration_markers": count,
            "x_fit": [ax_a, ax_b],
            "row_fit": [row_a, row_b],
            "max_residual_x": max_x,
            "max_residual_y": max_y,
            "positions_added": len(added),
            "positions_existing": existing,
            "problems": problems,
        }
        db.add(
            AuditLog(
                project_id=project.id,
                actor_id=actor.id,
                action="component_pd1_additional_positions_placed",
                entity="ComponentMapPosition",
                entity_id=str(uuid.uuid4()),
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )
        db.commit()

        manifest = json.loads(
            (args.maps_root / "cau-chinh-pd1" / "manifest.json").read_text(encoding="utf-8")
        )
        sheet_markers = next(
            (item.get("markers", []) for item in manifest["sheets"] if item["id"] == "plan"),
            [],
        )
        _overlay(
            plan_image,
            [m for m in sheet_markers if m.get("type") == "pile"],
            [item for item in added if item["sheet"] == PLAN_SHEET],
            args.maps_root / "expansion" / "placements" / "cau-chinh-pd1-plan-additional.png",
        )
        tk02_markers = next(
            (item.get("markers", []) for item in manifest["sheets"] if item["id"] == "tk02-pd1"),
            [],
        )
        _overlay(
            tk02_image,
            tk02_markers,
            [item for item in added if item["sheet"] == TK02_SHEET],
            args.maps_root / "expansion" / "placements" / "cau-chinh-pd1-tk02-pd1-additional.png",
        )
        print("PD1 ADDITIONAL COMMITTED")
        print(
            json.dumps(
                {
                    "calibration_markers": count,
                    "x_fit": [ax_a, ax_b],
                    "row_fit": [row_a, row_b],
                    "max_residual_x": max_x,
                    "max_residual_y": max_y,
                    "positions_added": len(added),
                    "positions_existing": existing,
                    "problems": problems,
                    "committed_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
