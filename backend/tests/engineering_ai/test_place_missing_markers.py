"""Synthetic tests for scripts/place_missing_markers.py."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.component_models import (
    ComponentAlias,
    ComponentMapPosition,
    RepairScope,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.database import Base
from app.core.models import AuditLog, Project, ProjectMember, User

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "place_missing_markers.py"
PROJECT_NAME = "DAP synthetic map"


def _load_script():
    spec = importlib.util.spec_from_file_location("place_missing_markers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _database_url(path: Path) -> str:
    return "sqlite:///" + path.as_posix()


def _seed(database: Path) -> None:
    engine = create_engine(_database_url(database), future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="u1", username="tester", password_hash="x", role="admin"))
        db.add(Project(id="p1", name=PROJECT_NAME, status="active"))
        db.add(ProjectMember(id="m1", project_id="p1", user_id="u1", role="project_manager"))
        zone = StructureZone(project_id="p1", name="Cầu dẫn", name_key="cau dan")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=7, source_code="PD7")
        db.add(segment)
        db.flush()
        db.add(
            StructuralComponent(
                id="pile-1",
                project_id="p1",
                segment_id=segment.id,
                type="pile",
                raw_code="N238",
                canonical_code="N238",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="u1",
            )
        )
        db.commit()


def _maps(maps_root: Path) -> None:
    folder = maps_root / "cau-dan-pd07"
    folder.mkdir(parents=True)
    Image.new("RGB", (100, 100), "white").save(folder / "plan.jpg")
    manifest = {
        "project_id": "p1",
        "sheets": [
            {
                "id": "plan",
                "title": "PD7 plan",
                "drawing": "TK-91",
                "page": 97,
                "image": "plan.jpg",
                "zone": "Cầu dẫn",
                "segment": 7,
                "markers": [],
            }
        ],
        "review": [],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _placements(path: Path, corner_csv: Path) -> None:
    corner_csv.write_text(
        "page;drawing;zone;segment;group;corner_type;source_row;location_code\n"
        "104;TK-98;Cầu dẫn;7;III;01;1;Q-235\n",
        encoding="utf-8",
    )
    doc = {
        "schema": "dap-placements/v1",
        "project_id": "p1",
        "sheets": {
            "cau-dan-pd07-plan": {
                "drawing": "TK-91",
                "page": 97,
                "zone": "Cầu dẫn",
                "segment": 7,
                "markers": [
                    {
                        "code": "N238",
                        "type": "pile",
                        "points": [[0.5, 0.5]],
                        "note": "synthetic pile",
                    },
                    {
                        "code": "Q-235",
                        "type": "beam",
                        "points": [[0.8, 0.5], [0.808, 0.5]],
                        "note": "synthetic corner",
                    },
                ],
            }
        },
        "corner_catalog": [
            {
                "code": "Q-235",
                "zone": "Cầu dẫn",
                "segment": 7,
                "source_row": 1,
                "drawing": "TK-98",
                "page": 104,
            }
        ],
        "unresolved": [],
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _run(database: Path, maps_root: Path, placements: Path, corner_csv: Path, *extra: str):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--database",
            _database_url(database),
            "--project",
            PROJECT_NAME,
            "--maps-root",
            str(maps_root),
            "--placements",
            str(placements),
            "--corner-source",
            str(corner_csv),
            *extra,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_validate_marker_rejects_wrong_shape_and_bounds():
    module = _load_script()
    module._validate_marker({"code": "N238", "type": "pile", "points": [[0.5, 0.5]]}, "s")
    module._validate_marker({"code": "Q-235", "type": "beam", "points": [[0.5, 0.5], [0.6, 0.5]]}, "s")
    for marker in (
        {"code": "N238", "type": "pile", "points": [[0.5, 0.5], [0.6, 0.5]]},
        {"code": "Q-235", "type": "beam", "points": [[0.5, 0.5]]},
        {"code": "N238", "type": "pile", "points": [[1.5, 0.5]]},
        {"code": "N238", "type": "corner", "points": [[0.5, 0.5]]},
    ):
        try:
            module._validate_marker(marker, "s")
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid marker: {marker}")


def test_preview_commit_and_idempotent(tmp_path):
    database = tmp_path / "app.db"
    maps_root = tmp_path / "maps"
    placements = tmp_path / "placements.json"
    corner_csv = tmp_path / "corners.csv"
    _seed(database)
    _maps(maps_root)
    _placements(placements, corner_csv)

    preview = _run(database, maps_root, placements, corner_csv)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "positions to add: 2" in preview.stdout
    assert "components to create: 1" in preview.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert db.scalar(select(ComponentMapPosition)) is None
        assert db.scalar(select(ComponentAlias)) is None

    committed = _run(database, maps_root, placements, corner_csv, "--commit")
    assert committed.returncode == 0, committed.stdout + committed.stderr
    assert '"positions_added": 2' in committed.stdout
    assert '"components_created": 1' in committed.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        corner = db.scalar(select(StructuralComponent).where(StructuralComponent.canonical_code == "Q-235"))
        assert corner is not None
        assert corner.type == "beam"
        assert corner.verification == "NEEDS_REVIEW"
        assert corner.record_origin == "MANUAL_ENTRY"
        assert corner.source_row == 1
        assert corner.source_hash == hashlib.sha256(corner_csv.read_bytes()).hexdigest()
        scope = db.scalar(select(RepairScope).where(RepairScope.component_id == corner.id))
        assert scope is not None and scope.verification == "NEEDS_REVIEW"
        assert db.scalar(select(ComponentAlias).where(ComponentAlias.alias == "Q-235"))
        positions = list(db.scalars(select(ComponentMapPosition)).all())
        assert len(positions) == 2
        assert {item.status for item in positions} == {"DRAFT"}
        assert {item.source for item in positions} == {"ai_extracted"}
        assert db.scalar(select(AuditLog).where(AuditLog.action == "component_map_positions_placed"))

    rerun = _run(database, maps_root, placements, corner_csv, "--commit")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert '"positions_added": 0' in rerun.stdout
    assert '"components_created": 0' in rerun.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert len(list(db.scalars(select(ComponentMapPosition)).all())) == 2
