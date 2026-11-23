"""Preview/commit import of reviewed per-pile design parameters from CSV.

The source workbook export is reviewed and private; this module only reads it at
runtime and stores numeric values plus provenance.  No source rows are bundled.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import unicodedata
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from .component_models import (
    ComponentAlias,
    ComponentDesignParameter,
    Segment,
    StructuralComponent,
    StructureZone,
)
from .models import AuditLog

PARAMETER_COLUMNS = (
    ("L1_m", "m"),
    ("L2_m", "m"),
    ("L3_m", "m"),
    ("L4_m", "m"),
    ("t_cm", "cm"),
    ("n", None),
    ("a_mm", "mm"),
    ("b_m", "m"),
)
T_PARAMETER = "t_cm"


def _zone_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _code_key(value: str) -> str:
    return (value or "").strip().upper()


def _number(value: str) -> Optional[float]:
    text = (value or "").strip().replace(" ", "")
    if not text:
        return None
    return float(text.replace(",", "."))


def _int(value: str) -> Optional[int]:
    text = (value or "").strip()
    return int(text) if text else None


def read_source(path: str) -> tuple[list[dict[str, str]], str]:
    raw = open(path, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";")), digest


def _parameter_rows(row: dict[str, str]) -> dict[str, float]:
    values: dict[str, float] = {}
    for name, _unit in PARAMETER_COLUMNS:
        value = _number(row.get(name, ""))
        if value is not None:
            values[name] = value
    return values


def prepare_import(db: Session, project_id: str, csv_path: str) -> dict[str, Any]:
    rows, digest = read_source(csv_path)
    components = db.execute(
        select(StructuralComponent, Segment, StructureZone)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .where(
            StructuralComponent.project_id == project_id,
            StructuralComponent.type == "pile",
            StructureZone.project_id == project_id,
        )
    ).all()
    aliases: dict[str, list[str]] = defaultdict(list)
    for component_id, alias in db.execute(
        select(ComponentAlias.component_id, ComponentAlias.alias).where(
            ComponentAlias.project_id == project_id
        )
    ):
        aliases[component_id].append(_code_key(alias))

    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for component, segment, zone in components:
        item = {
            "id": component.id,
            "code": component.canonical_code,
            "zone": zone.name,
            "segment": segment.number,
        }
        keys = {
            _code_key(component.canonical_code),
            _code_key(component.raw_code),
            *aliases.get(component.id, []),
        }
        for key in keys:
            by_key[(_zone_key(zone.name), key)].append(item)

    unmatched: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    matched: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalid: list[dict[str, Any]] = []
    for row in rows:
        zone = row.get("zone_printed", "")
        code = _code_key(row.get("code_printed", ""))
        hits = {item["id"]: item for item in by_key.get((_zone_key(zone), code), [])}
        if not hits:
            unmatched.append(
                {
                    "zone": zone,
                    "code": row.get("code_printed", ""),
                    "drawing": row.get("drawing", ""),
                    "page": _int(row.get("page", "")),
                    "source_row": _int(row.get("source_data_row", "")),
                }
            )
            continue
        if len(hits) > 1:
            ambiguous.append(
                {
                    "zone": zone,
                    "code": row.get("code_printed", ""),
                    "candidates": sorted(hits.values(), key=lambda item: item["id"]),
                }
            )
            continue
        try:
            _parameter_rows(row)
        except ValueError:
            invalid.append(
                {
                    "zone": zone,
                    "code": row.get("code_printed", ""),
                    "source_row": _int(row.get("source_data_row", "")),
                }
            )
            continue
        matched[next(iter(hits))].append(row)

    conflicts: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []
    component_by_id = {
        item["id"]: item for items in by_key.values() for item in items
    }
    for component_id, source_rows in matched.items():
        per_name: dict[str, set[float]] = defaultdict(set)
        for row in source_rows:
            for name, value in _parameter_rows(row).items():
                per_name[name].add(round(value, 4))
        conflicting = {name: sorted(values) for name, values in per_name.items() if len(values) > 1}
        if conflicting:
            info = component_by_id[component_id]
            conflicts.append(
                {
                    "component_id": component_id,
                    "code": info["code"],
                    "zone": info["zone"],
                    "reason": "same component with different values",
                    "values": conflicting,
                }
            )
            continue
        first = source_rows[0]
        for name, unit in PARAMETER_COLUMNS:
            value = _parameter_rows(first).get(name)
            if value is None:
                continue
            planned.append(
                {
                    "component_id": component_id,
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "source_drawing": first.get("drawing") or None,
                    "source_page": _int(first.get("page", "")),
                    "source_row": _int(first.get("source_data_row", "")),
                    "source_file_hash": digest,
                }
            )

    has_table = inspect(db.get_bind()).has_table("component_design_parameters")
    existing: dict[tuple[str, str], ComponentDesignParameter] = {}
    if has_table:
        for parameter in db.scalars(select(ComponentDesignParameter)):
            existing[(parameter.component_id, parameter.name)] = parameter

    to_insert: list[dict[str, Any]] = []
    unchanged = 0
    existing_conflicts: list[dict[str, Any]] = []
    for item in planned:
        current = existing.get((item["component_id"], item["name"]))
        if current is None:
            to_insert.append(item)
        elif abs(float(current.value) - float(item["value"])) < 1e-9:
            unchanged += 1
        else:
            existing_conflicts.append(
                {
                    "component_id": item["component_id"],
                    "name": item["name"],
                    "stored": current.value,
                    "incoming": item["value"],
                }
            )
    if existing_conflicts:
        conflicts.extend(
            {
                "component_id": item["component_id"],
                "code": next(
                    (row["code"] for row in component_by_id.values() if row["id"] == item["component_id"]),
                    "",
                ),
                "zone": next(
                    (row["zone"] for row in component_by_id.values() if row["id"] == item["component_id"]),
                    "",
                ),
                "reason": "different from stored value; not overwritten",
                "values": {item["name"]: [item["stored"], item["incoming"]]},
            }
            for item in existing_conflicts
        )

    return {
        "project_id": project_id,
        "csv_rows": len(rows),
        "source_file_hash": digest,
        "matched_rows": sum(len(items) for items in matched.values()),
        "matched_components": len(matched),
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "invalid": invalid,
        "conflicts": conflicts,
        "parameters": to_insert,
        "planned_parameters": len(planned),
        "unchanged": unchanged,
        "existing_table": has_table,
        "components_with_t": sum(
            1 for component_id in matched if any(
                item["component_id"] == component_id and item["name"] == T_PARAMETER
                for item in planned
            )
        ),
    }


def commit_import(
    db: Session, preview: dict[str, Any], actor_id: str
) -> dict[str, Any]:
    if not preview["existing_table"]:
        raise RuntimeError(
            "component_design_parameters does not exist; run alembic upgrade head first"
        )
    inserted = 0
    for item in preview["parameters"]:
        db.add(
            ComponentDesignParameter(
                project_id=preview["project_id"],
                component_id=item["component_id"],
                name=item["name"],
                value=item["value"],
                unit=item["unit"],
                source_drawing=item["source_drawing"],
                source_page=item["source_page"],
                source_row=item["source_row"],
                source_file_hash=item["source_file_hash"],
                created_by=actor_id,
            )
        )
        inserted += 1
    summary = {
        "inserted": inserted,
        "unchanged": preview["unchanged"],
        "conflicts": len(preview["conflicts"]),
        "unmatched": len(preview["unmatched"]),
        "ambiguous": len(preview["ambiguous"]),
    }
    db.add(
        AuditLog(
            project_id=preview["project_id"],
            actor_id=actor_id,
            action="component_design_parameters_imported",
            entity="Project",
            entity_id=preview["project_id"],
            detail=json.dumps(
                {
                    **summary,
                    "source_file_hash": preview["source_file_hash"],
                    "csv_rows": preview["csv_rows"],
                }
            ),
        )
    )
    db.commit()
    return summary
