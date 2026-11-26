"""Synthetic tests for scripts/add_fender_panels.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.component_models import (
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
from app.core.database import Base
from app.core.models import AuditLog, Project, ProjectMember, User

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "add_fender_panels.py"
PROJECT_NAME = "DAP synthetic fenders"


def _load_script():
    spec = importlib.util.spec_from_file_location("add_fender_panels", SCRIPT)
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
        zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        db.add(zone)
        db.flush()
        db.add(Segment(id="seg3", zone_id=zone.id, number=3, source_code="PD3"))
        db.commit()


def _workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Tấm tựa tàu"
    ws.append(
        [
            "page",
            "drawing",
            "group",
            "code_by_table_title",
            "code_in_quantity_column",
            "source_row",
            "unit",
            "work_item",
            "quantity_raw",
            "review_status",
        ]
    )
    for position in range(1, 31):
        ws.append(
            [
                116,
                "TK-110",
                "I",
                "K-111-112",
                "K-135-136",
                position,
                "m²",
                f"Item {position}",
                f"{position},5",
                "SOURCE_CODE_CONFLICT",
            ]
        )
    for position in range(1, 31):
        ws.append(
            [
                118,
                "TK-112",
                "I",
                "K-135-136",
                "K-135-136",
                position,
                "m²",
                f"Item {position}",
                "-" if position == 3 else f"{position},5",
                "",
            ]
        )
    for position in range(1, 6):
        ws.append(
            [
                119,
                "TK-113",
                "II",
                "K-1",
                "K-1",
                position,
                "m²",
                f"K1 item {position}",
                f"{position},25",
                "",
            ]
        )
    wb.save(path)


def _maps(maps_root: Path) -> None:
    folder = maps_root / "cau-chinh-pd3"
    folder.mkdir(parents=True)
    Image.new("RGB", (100, 100), "white").save(folder / "plan.jpg")
    manifest = {
        "project_id": "p1",
        "sheets": [
            {
                "id": "plan",
                "title": "PD3 plan",
                "drawing": "TK-33",
                "page": 39,
                "image": "plan.jpg",
                "zone": "Cầu chính",
                "segment": 3,
                "markers": [],
            }
        ],
        "review": [],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _run(database: Path, workbook: Path, maps_root: Path, *extra: str):
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
            "--workbook",
            str(workbook),
            "--maps-root",
            str(maps_root),
            *extra,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_rows_reads_three_panels(tmp_path):
    module = _load_script()
    workbook = tmp_path / "book.xlsx"
    _workbook(workbook)
    rows = module._rows(workbook)
    assert [len(rows[code]) for code in module.PANELS] == [30, 30, 5]
    assert rows["K-111-112"][0]["quantity"] == 1.5
    assert rows["K-135-136"][2]["quantity"] is None
    assert rows["K-1"][0]["name"] == "K1 item 1"


def test_preview_commit_and_idempotent(tmp_path):
    database = tmp_path / "app.db"
    workbook = tmp_path / "book.xlsx"
    maps_root = tmp_path / "maps"
    _seed(database)
    _workbook(workbook)
    _maps(maps_root)

    preview = _run(database, workbook, maps_root)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "components to create: 3" in preview.stdout
    assert "stages to add: 65" in preview.stdout
    assert "positions to add: 2" in preview.stdout
    assert "K-1: no plan label found" in preview.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert db.scalar(select(StructuralComponent)) is None
        assert db.scalar(select(ComponentStage)) is None
        assert db.scalar(select(ComponentMapPosition)) is None

    committed = _run(database, workbook, maps_root, "--commit")
    assert committed.returncode == 0, committed.stdout + committed.stderr
    assert '"components_created": 3' in committed.stdout
    assert '"stages_added": 65' in committed.stdout
    assert '"positions_added": 2' in committed.stdout
    assert '"definitions_created": 35' in committed.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        group = db.scalar(select(DesignGroup))
        assert group is not None and group.name == "Tấm tựa tàu"
        components = {
            item.canonical_code: item
            for item in db.scalars(select(StructuralComponent)).all()
        }
        assert set(components) == {"K-111-112", "K-135-136", "K-1"}
        assert {item.type for item in components.values()} == {"beam"}
        assert {item.design_group_id for item in components.values()} == {group.id}
        assert {item.verification for item in components.values()} == {"NEEDS_REVIEW"}
        assert len(list(db.scalars(select(ComponentAlias)).all())) == 3
        assert len(list(db.scalars(select(RepairScope)).all())) == 3
        definitions = list(db.scalars(select(StageDefinition)).all())
        assert len(definitions) == 35
        stages = list(db.scalars(select(ComponentStage)).all())
        assert len(stages) == 65
        by_component = {}
        for stage in stages:
            by_component.setdefault(stage.component_id, []).append(stage)
        assert len(by_component[components["K-111-112"].id]) == 30
        assert len(by_component[components["K-135-136"].id]) == 30
        assert len(by_component[components["K-1"].id]) == 5
        first = [
            stage
            for stage in by_component[components["K-111-112"].id]
            if stage.design_quantity["quantity"] == 1.5
        ]
        assert first and "SOURCE_CODE_CONFLICT" in first[0].design_quantity["note"]
        assert all(
            stage.design_quantity["scope"] == "COMPONENT" for stage in stages
        )
        positions = list(db.scalars(select(ComponentMapPosition)).all())
        assert len(positions) == 2
        assert {item.sheet_id for item in positions} == {"cau-chinh-pd3-plan"}
        assert {item.status for item in positions} == {"DRAFT"}
        placed = {item.component_id for item in positions}
        assert components["K-1"].id not in placed
        assert db.scalar(select(AuditLog).where(AuditLog.action == "component_fender_panels_setup"))

    rerun = _run(database, workbook, maps_root, "--commit")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert '"stages_added": 0' in rerun.stdout
    assert '"positions_added": 0' in rerun.stdout
    assert '"definitions_created": 0' in rerun.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert len(list(db.scalars(select(ComponentStage)).all())) == 65
        assert len(list(db.scalars(select(ComponentMapPosition)).all())) == 2
