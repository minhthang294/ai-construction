#!/usr/bin/env python3
"""Promote owner-approved DAP candidate maps into live drawing-map folders.

Preview is read-only. ``--commit`` copies each candidate plan image (never the
``*-candidates`` annotated overlay), writes ``manifest.json`` in the same schema
as ``data/storage/dap-maps/pd2``, and never touches ``pd2``. Coordinates stay
normalized ``[0,1]``. Only codes present in the project catalog are promoted;
the rest are printed and recorded in the manifest ``review`` list.

Examples:
  python scripts/promote_map_candidates.py \
    --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)"

  # add --commit to write the live folders
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.component_models import (  # noqa: E402
    ComponentAlias,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.models import Project  # noqa: E402

DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
DEFAULT_SOURCE = DEFAULT_MAPS / "expansion"
IMAGE_NAME = re.compile(r"^[a-z0-9-]{1,60}\.(jpg|jpeg)$")
SHEET_ID = re.compile(r"^[a-z0-9_-]{1,80}$")
MAP_KEY = re.compile(r"^[a-z0-9_-]{1,40}$")


def fold(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def norm_code(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().upper()


def normalize_type(value: str | None) -> str | None:
    text = fold(value)
    if text in ("pile", "beam"):
        return text
    if text in ("corner_beam", "corner-beam", "corner"):
        return "beam"
    return None


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    type: str
    canonical: str
    zone: str
    segment: int
    codes: frozenset[str]


class Catalog:
    def __init__(self, entries: Iterable[CatalogEntry]):
        self.entries = list(entries)
        self.by_code: dict[str, list[CatalogEntry]] = defaultdict(list)
        for entry in self.entries:
            for code in entry.codes:
                self.by_code[code].append(entry)

    def resolve(
        self,
        raw_type: str | None,
        raw_code: str | None,
        zone: str | None,
        segment: int | None,
        *,
        exact_segment: bool = True,
    ) -> tuple[CatalogEntry | None, str | None]:
        type_ = normalize_type(raw_type)
        code = norm_code(raw_code)
        if type_ is None or not code:
            return None, "unsupported type/code"
        matches = self.by_code.get(code, [])
        exact = [
            entry
            for entry in matches
            if entry.type == type_
            and fold(entry.zone) == fold(zone)
            and entry.segment == segment
        ]
        if len(exact) == 1:
            return exact[0], None
        if len(exact) > 1:
            return None, "ambiguous in this zone/segment"
        if exact_segment:
            return None, "not in the project catalog at this zone/segment"
        wide = [entry for entry in matches if entry.type == type_]
        unique = {(entry.zone, entry.segment): entry for entry in wide}
        if len(unique) == 1:
            entry = next(iter(unique.values()))
            return entry, f"catalog segment {entry.zone} {entry.segment}"
        if len(unique) > 1:
            return None, "ambiguous across segments"
        return None, "not in the project catalog"


@dataclass
class CandidateSheet:
    key: str
    sheet_id: str
    title: str
    drawing: str
    page: int
    image: Path
    zone: str | None
    segment: int | None
    markers: list[dict[str, Any]]
    exact_segment: bool = True
    reviews: list[dict[str, str]] = field(default_factory=list)


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def load_catalog(db: Session, project_id: str) -> Catalog:
    rows = db.execute(
        select(StructuralComponent, StructureZone.name, Segment.number)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(StructuralComponent.project_id == project_id)
    ).all()
    aliases: dict[str, set[str]] = defaultdict(set)
    for alias, component_id in db.execute(
        select(ComponentAlias.alias, ComponentAlias.component_id).where(
            ComponentAlias.project_id == project_id
        )
    ):
        aliases[component_id].add(norm_code(alias))
    entries = []
    for component, zone, segment in rows:
        codes = {
            norm_code(component.canonical_code),
            norm_code(component.raw_code),
            *aliases.get(component.id, set()),
        }
        entries.append(
            CatalogEntry(
                id=component.id,
                type=component.type,
                canonical=norm_code(component.canonical_code),
                zone=zone,
                segment=segment,
                codes=frozenset(code for code in codes if code),
            )
        )
    return Catalog(entries)


def _points_ok(type_: str, points: Any) -> bool:
    if not isinstance(points, list) or not points or len(points) > 30:
        return False
    if type_ == "pile" and len(points) != 1:
        return False
    if type_ == "beam" and len(points) < 2:
        return False
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return False
        x, y = point
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False
        if not (0 <= float(x) <= 1 and 0 <= float(y) <= 1):
            return False
    return True


def build_sheet(
    spec: CandidateSheet, catalog: Catalog
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    """Convert one candidate sheet to a live manifest sheet.

    Returns ``(sheet, stats, reviews)``. Pure: no file or database writes.
    """
    promoted: list[dict[str, Any]] = []
    dropped: list[tuple[str, str, str]] = []
    corrected: list[tuple[str, str]] = []
    for marker in spec.markers:
        zone = marker.get("zone") if marker.get("zone") is not None else spec.zone
        segment = (
            marker.get("segment")
            if marker.get("segment") is not None
            else spec.segment
        )
        entry, reason = catalog.resolve(
            marker.get("type"),
            marker.get("code"),
            zone,
            segment,
            exact_segment=spec.exact_segment,
        )
        if entry is None:
            dropped.append(
                (norm_code(marker.get("code")), str(marker.get("type")), reason or "unmatched")
            )
            continue
        if not _points_ok(entry.type, marker.get("points")):
            dropped.append(
                (
                    norm_code(marker.get("code")),
                    str(marker.get("type")),
                    f"invalid points for {entry.type}",
                )
            )
            continue
        if reason:
            corrected.append((entry.canonical, reason))
        promoted.append(
            {
                "code": entry.canonical,
                "type": entry.type,
                "points": [[float(x), float(y)] for x, y in marker["points"]],
                "zone": entry.zone,
                "segment": entry.segment,
                "location_review": False,
            }
        )

    zones = {fold(item["zone"]) for item in promoted}
    segments = {item["segment"] for item in promoted}
    if promoted and len(zones) == 1 and len(segments) == 1:
        sheet_zone = promoted[0]["zone"]
        sheet_segment = promoted[0]["segment"]
    elif not promoted:
        sheet_zone, sheet_segment = spec.zone, spec.segment
    else:
        sheet_zone = sheet_segment = None

    sheet = {
        "id": spec.sheet_id,
        "title": spec.title,
        "drawing": spec.drawing,
        "page": spec.page,
        "image": spec.image.name.lower(),
        "zone": sheet_zone,
        "segment": sheet_segment,
        "markers": promoted,
    }
    reviews = list(spec.reviews)
    if dropped:
        reviews.append(
            {
                "code": ", ".join(code for code, _, _ in dropped),
                "scope": f"{spec.key}/{spec.sheet_id}",
                "reason": "; ".join(sorted({reason for _, _, reason in dropped})),
            }
        )
    if corrected:
        reviews.append(
            {
                "code": ", ".join(code for code, _ in corrected),
                "scope": f"{spec.key}/{spec.sheet_id}",
                "reason": "; ".join(sorted({reason for _, reason in corrected})),
            }
        )
    stats = {
        "markers": len(spec.markers),
        "promoted": len(promoted),
        "dropped": len(dropped),
        "corrected": len(corrected),
        "dropped_detail": dropped,
        "corrected_detail": corrected,
    }
    return sheet, stats, reviews


def _sheet_id(raw: str, segment: int) -> str:
    value = fold(raw)
    value = re.sub(rf"^pd0*{segment}-", "", value)
    value = re.sub(r"-(plan-label|plan)$", "", value)
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-")
    return value or "plan"


def _candidate_marker(
    marker: dict[str, Any],
    *,
    code_key: str = "canonical_code",
    zone: str | None = None,
    segment: int | None = None,
    force_zone_segment: bool = False,
) -> dict[str, Any]:
    return {
        "code": marker[code_key],
        "type": marker.get("type"),
        "points": marker.get("points") or [],
        "zone": zone if force_zone_segment else marker.get("zone", zone),
        "segment": segment if force_zone_segment else marker.get("segment", segment),
    }


def discover(source_root: Path) -> tuple[list[CandidateSheet], list[tuple[str, str]]]:
    """Read the approved candidate folders. No writes."""
    specs: list[CandidateSheet] = []
    skipped: list[tuple[str, str]] = []

    cau_chinh = source_root / "cau-chinh" / "candidates.json"
    if cau_chinh.is_file():
        data = json.loads(cau_chinh.read_text(encoding="utf-8"))
        for sheet in data.get("sheets", []):
            key = f"cau-chinh-{fold(sheet.get('id'))}"
            markers = [
                _candidate_marker(marker, zone=sheet.get("zone"), segment=sheet.get("segment"))
                for marker in sheet.get("markers", [])
            ]
            specs.append(
                CandidateSheet(
                    key=key,
                    sheet_id="plan",
                    title=sheet["title"],
                    drawing=sheet["drawing"],
                    page=int(sheet["page"]),
                    image=cau_chinh.parent / sheet["image"],
                    zone=sheet.get("zone"),
                    segment=sheet.get("segment"),
                    markers=markers,
                    exact_segment=True,
                )
            )

    bunke = source_root / "bunke" / "bunke-candidates.json"
    if bunke.is_file():
        data = json.loads(bunke.read_text(encoding="utf-8"))
        markers = []
        for pile in data.get("piles", []):
            if pile.get("points"):
                markers.append(_candidate_marker(pile))
        for beam in data.get("beams", []):
            if beam.get("points"):
                markers.append(
                    _candidate_marker(
                        beam, zone="Bunke", segment=1, force_zone_segment=True
                    )
                )
        unresolved = [
            pile["canonical_code"] for pile in data.get("piles", [])
            if not pile.get("points")
        ]
        reviews = []
        if unresolved:
            reviews.append(
                {
                    "code": ", ".join(unresolved),
                    "scope": "bunke/plan",
                    "reason": "no candidate point; not placed on the map",
                }
            )
        source = data["source"]
        specs.append(
            CandidateSheet(
                key="bunke",
                sheet_id="plan",
                title="Bunke – mặt bằng TK-32 (inset)",
                drawing=source["map_drawing"],
                page=int(source["map_page"]),
                image=bunke.parent / data["image"]["file"],
                zone="Bunke",
                segment=1,
                markers=markers,
                exact_segment=True,
                reviews=reviews,
            )
        )

    cau_dan = source_root / "cau-dan"
    index = cau_dan / "index.json"
    segments = []
    if index.is_file():
        data = json.loads(index.read_text(encoding="utf-8"))
        segments = [int(item["segment"]) for item in data.get("segments", [])]
    elif cau_dan.is_dir():
        segments = sorted(
            int(path.parent.name[2:])
            for path in cau_dan.glob("pd*/candidates.json")
            if path.parent.name[2:].isdigit()
        )
    for segment in segments:
        path = cau_dan / f"pd{segment:02d}" / "candidates.json"
        if not path.is_file():
            skipped.append((f"cau-dan-pd{segment:02d}", "candidates.json is missing"))
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for sheet in data.get("sheets", []):
            key = f"cau-dan-pd{segment:02d}"
            markers = [
                _candidate_marker(
                    marker,
                    zone=sheet.get("zone") or data.get("zone"),
                    segment=sheet.get("segment")
                    if sheet.get("segment") is not None
                    else data.get("segment"),
                )
                for marker in sheet.get("markers", [])
            ]
            specs.append(
                CandidateSheet(
                    key=key,
                    sheet_id=_sheet_id(sheet["id"], segment),
                    title=sheet["title"],
                    drawing=sheet["drawing"],
                    page=int(sheet["page"]),
                    image=path.parent / sheet["image"],
                    zone=sheet.get("zone") or data.get("zone"),
                    segment=sheet.get("segment")
                    if sheet.get("segment") is not None
                    else data.get("segment"),
                    markers=markers,
                    exact_segment=False,
                )
            )

    tam_tua = source_root / "tam-tua-tau" / "manifest.json"
    if tam_tua.is_file():
        skipped.append(
            (
                "tam-tua-tau",
                "candidate schema needs the fender_panel type; the drawing-map API supports pile/beam only",
            )
        )

    known = {"cau-chinh", "bunke", "cau-dan", "tam-tua-tau"}
    if source_root.is_dir():
        for folder in sorted(source_root.iterdir()):
            if folder.is_dir() and folder.name not in known:
                if any(folder.glob("*.json")):
                    skipped.append((folder.name, "unsupported candidate family"))
    return specs, skipped


def _image_name(path: Path) -> str:
    name = path.name.lower()
    if "candidate" in name:
        raise SystemExit(f"Refusing the annotated candidate image: {path}")
    if not IMAGE_NAME.fullmatch(name):
        raise SystemExit(f"Image name does not fit the drawing-map schema: {path.name}")
    return name


def promote(
    specs: list[CandidateSheet],
    catalog: Catalog,
    project_id: str,
    maps_root: Path,
    *,
    commit: bool,
) -> list[dict[str, Any]]:
    by_key: dict[str, list[CandidateSheet]] = defaultdict(list)
    for spec in specs:
        by_key[spec.key].append(spec)
    results = []
    for key in sorted(by_key):
        if key == "pd2":
            raise SystemExit("Refusing to touch pd2")
        if not MAP_KEY.fullmatch(key):
            raise SystemExit(f"Invalid map key: {key}")
        sheets = []
        reviews = []
        sheet_ids = set()
        image_names = set()
        stats = {"markers": 0, "promoted": 0, "dropped": 0, "corrected": 0}
        dropped_detail = []
        corrected_detail = []
        for spec in by_key[key]:
            if spec.sheet_id in sheet_ids:
                raise SystemExit(f"Duplicate sheet id {key}-{spec.sheet_id}")
            sheet_ids.add(spec.sheet_id)
            image_name = _image_name(spec.image)
            if image_name in image_names:
                raise SystemExit(f"Duplicate image name {image_name} in {key}")
            image_names.add(image_name)
            if not spec.image.is_file():
                raise SystemExit(f"Candidate image not found: {spec.image}")
            sheet, sheet_stats, sheet_reviews = build_sheet(spec, catalog)
            sheet["image"] = image_name
            sheets.append(sheet)
            reviews.extend(sheet_reviews)
            for name in ("markers", "promoted", "dropped", "corrected"):
                stats[name] += sheet_stats[name]
            dropped_detail.extend(
                [(spec.sheet_id, *item) for item in sheet_stats["dropped_detail"]]
            )
            corrected_detail.extend(
                [(spec.sheet_id, *item) for item in sheet_stats["corrected_detail"]]
            )
        manifest = {"project_id": project_id, "sheets": sheets, "review": reviews}
        out_dir = maps_root / key
        if commit:
            out_dir.mkdir(parents=True, exist_ok=True)
            for spec in by_key[key]:
                shutil.copyfile(spec.image, out_dir / _image_name(spec.image))
            (out_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        results.append(
            {
                "key": key,
                "sheets": len(sheets),
                "images": len(image_names),
                "stats": stats,
                "dropped": dropped_detail,
                "corrected": corrected_detail,
                "written": commit,
            }
        )
    return results


def _print_report(
    results: list[dict[str, Any]],
    skipped: list[tuple[str, str]],
    *,
    commit: bool,
    maps_root: Path,
) -> None:
    print("PROMOTION COMMIT" if commit else "PROMOTION PREVIEW (no writes)")
    print(f"  Maps root: {maps_root}")
    for result in results:
        stats = result["stats"]
        print(
            f"  {result['key']:<18} sheets {result['sheets']:>2}  "
            f"markers {stats['markers']:>3}  promoted {stats['promoted']:>3}  "
            f"dropped {stats['dropped']:>2}  corrected {stats['corrected']:>2}"
        )
        if result["dropped"]:
            grouped: dict[str, list[str]] = defaultdict(list)
            for sheet_id, code, _, reason in result["dropped"]:
                grouped[reason].append(f"{code} [{sheet_id}]")
            for reason, codes in sorted(grouped.items()):
                print(f"    dropped ({reason}): {', '.join(sorted(codes))}")
        if result["corrected"]:
            for sheet_id, code, reason in result["corrected"]:
                print(f"    corrected {code} [{sheet_id}]: {reason}")
    total = {
        name: sum(result["stats"][name] for result in results)
        for name in ("markers", "promoted", "dropped", "corrected")
    }
    print(
        f"  TOTAL keys {len(results)}, sheets {sum(r['sheets'] for r in results)}, "
        f"images {sum(r['images'] for r in results)}, markers {total['markers']}, "
        f"promoted {total['promoted']}, dropped {total['dropped']}, "
        f"corrected {total['corrected']}"
    )
    for key, reason in skipped:
        print(f"  skipped {key}: {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.source_root.is_dir():
        print(f"Candidate root not found: {args.source_root}", file=sys.stderr)
        return 2
    specs, skipped = discover(args.source_root)
    if not specs:
        print("No approved candidate maps found", file=sys.stderr)
        return 2
    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        catalog = load_catalog(db, project.id)
        try:
            results = promote(
                specs,
                catalog,
                project.id,
                args.maps_root,
                commit=args.commit,
            )
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 2
    _print_report(results, skipped, commit=args.commit, maps_root=args.maps_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
