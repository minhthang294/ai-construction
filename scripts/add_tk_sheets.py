#!/usr/bin/env python3
"""Add owner-reviewed TK-02/TK-03/TK-09/TK-10 plan crops as live map sheets.

The config is ``data/storage/dap-maps/expansion/placements/tk-sheets.json``.
Preview is read-only. ``--commit`` crops the private PDF pages, adds/replaces
the sheets in the live manifests and writes PNG overlays plus a per-sheet
report. It never edits the DB, a source image or the PDF.

Examples:
  python scripts/add_tk_sheets.py --pdf "C:/.../bản vẽ scan_1.pdf"
  python scripts/add_tk_sheets.py --pdf "..." --commit
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    ROOT / "data" / "storage" / "dap-maps" / "expansion" / "placements" / "tk-sheets.json"
)
DEFAULT_MAPS = ROOT / "data" / "storage" / "dap-maps"
DEFAULT_OVERLAYS = (
    ROOT / "data" / "storage" / "dap-maps" / "expansion" / "placements"
)
IMAGE_NAME = re.compile(r"^[a-z0-9-]{1,60}\.(jpg|jpeg)$")


def _load(config: Path) -> dict:
    data = json.loads(config.read_text(encoding="utf-8"))
    if data.get("schema") != "dap-tk-sheets/v1":
        raise ValueError(f"unsupported schema: {data.get('schema')!r}")
    if not data.get("project_id") or not isinstance(data.get("sheets"), list):
        raise ValueError("project_id/sheets are missing")
    for sheet in data["sheets"]:
        for key in ("map", "id", "title", "drawing", "page", "image", "crop", "markers"):
            if key not in sheet:
                raise ValueError(f"sheet missing {key}: {sheet!r}")
        if not IMAGE_NAME.fullmatch(str(sheet["image"])):
            raise ValueError(f"{sheet['id']}: invalid image name {sheet['image']!r}")
        crop = sheet["crop"]
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or not all(isinstance(value, int) for value in crop)
            or crop[0] >= crop[1]
            or crop[2] >= crop[3]
        ):
            raise ValueError(f"{sheet['id']}: invalid crop {crop!r}")
        for marker in sheet["markers"]:
            if marker.get("type") not in ("pile", "beam") or not marker.get("code"):
                raise ValueError(f"{sheet['id']}: invalid marker {marker!r}")
            for point in marker.get("points", []):
                if len(point) != 2 or not all(0 <= float(value) <= 1 for value in point):
                    raise ValueError(f"{sheet['id']}/{marker['code']}: invalid point")
    return data


def _crop(pdf: Path, page: int, crop: List[int], out: Path) -> None:
    import fitz
    from PIL import Image

    document = fitz.open(pdf)
    try:
        pix = document[page - 1].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        document.close()
    x0, x1, y0, y1 = crop
    image.crop((x0, y0, x1, y1)).save(out, quality=90)


def _overlay(path: Path, sheet: dict, out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = ImageFont.load_default()
    for marker in sheet["markers"]:
        points = [
            (int(float(x) * width), int(float(y) * height))
            for x, y in marker["points"]
        ]
        if marker["type"] == "beam" and len(points) >= 2:
            draw.line(points, fill=(255, 0, 0), width=4)
        for x, y in points:
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(255, 0, 0), width=3)
        draw.text((points[0][0] + 8, points[0][1] - 16), marker["code"], fill=(0, 0, 255), font=font)
    image.save(out)


def _write_manifest(path: Path, manifest: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--maps-root", type=Path, default=DEFAULT_MAPS)
    parser.add_argument("--overlays", type=Path, default=DEFAULT_OVERLAYS)
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    try:
        data = _load(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 2

    problems: List[str] = []
    manifests: Dict[str, dict] = {}
    for sheet in data["sheets"]:
        folder = args.maps_root / sheet["map"]
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            problems.append(f"{sheet['map']}: manifest not found")
            continue
        manifest = manifests.get(sheet["map"])
        if manifest is None:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("project_id") != data["project_id"]:
                problems.append(f"{sheet['map']}: project mismatch")
                continue
            manifests[sheet["map"]] = manifest
        image = folder / sheet["image"]
        image_missing = not image.is_file()
        if image_missing and args.pdf is None:
            problems.append(f"{sheet['id']}: image missing and no --pdf")
            continue
        if image_missing and args.pdf is not None and not args.pdf.is_file():
            problems.append(f"{sheet['id']}: PDF not found")
            continue
        if args.commit and image_missing:
            _crop(args.pdf, int(sheet["page"]), sheet["crop"], image)
        sheets = [item for item in manifest.get("sheets", []) if item.get("id") != sheet["id"]]
        sheets.append(
            {
                "id": sheet["id"],
                "title": sheet["title"],
                "drawing": sheet["drawing"],
                "page": int(sheet["page"]),
                "image": sheet["image"],
                "zone": sheet.get("zone"),
                "segment": sheet.get("segment"),
                "markers": [
                    {
                        "code": marker["code"],
                        "type": marker["type"],
                        "points": marker["points"],
                        "zone": marker.get("zone") or sheet.get("zone") or "Cầu chính",
                        "segment": marker.get("segment") or sheet.get("segment") or 2,
                        "note": marker.get("note"),
                    }
                    for marker in sheet["markers"]
                ],
            }
        )
        manifest["sheets"] = sheets

    if not args.commit:
        print("TK SHEET PREVIEW (no writes)")
        for sheet in data["sheets"]:
            print(
                f"  {sheet['map']}/{sheet['id']}: {len(sheet['markers'])} markers "
                f"({sheet['drawing']} tr.{sheet['page']})"
            )
        print(f"  sheets: {len(data['sheets'])}; markers: {sum(len(s['markers']) for s in data['sheets'])}")
        if problems:
            print(f"  problems: {len(problems)}")
            for problem in problems:
                print(f"    {problem}")
        return 0 if not problems else 1

    for map_name, manifest in manifests.items():
        _write_manifest(args.maps_root / map_name / "manifest.json", manifest)

    args.overlays.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Bổ sung sheet TK-02/TK-03/TK-09/TK-10",
        "",
        "**Trạng thái:** DRAFT / cần xác nhận. Marker đọc trực quan trên bản scan; "
        "điểm đặt tại ô vuông cọc, không phải tọa độ khảo sát.",
        "",
        "| Map | Sheet | Bản vẽ | Trang | Marker |",
        "|---|---|---|---:|---:|",
    ]
    for sheet in data["sheets"]:
        folder = args.maps_root / sheet["map"]
        image = folder / sheet["image"]
        if image.is_file():
            _overlay(image, sheet, args.overlays / f"{sheet['map']}-{sheet['id']}.png")
        lines.append(
            f"| `{sheet['map']}` | `{sheet['id']}` | {sheet['drawing']} | {sheet['page']} | "
            f"{len(sheet['markers'])} |"
        )
    unresolved = data.get("unresolved", [])
    if unresolved:
        lines.extend(["", "## Chưa đặt được", ""])
        for item in unresolved:
            lines.append(f"- **{item.get('scope')}:** {item.get('items')} — {item.get('reason')}")
    if problems:
        lines.extend(["", "## Lỗi", ""])
        for problem in problems:
            lines.append(f"- {problem}")
    (args.overlays / "tk-sheets-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("TK SHEETS COMMITTED")
    print(json.dumps({"sheets": len(data["sheets"]), "problems": problems}, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
