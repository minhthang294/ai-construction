"""Synthetic tests for scripts/setup_corner_stages.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.component_models import (
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
SCRIPT = ROOT / "scripts" / "setup_corner_stages.py"
PROJECT_NAME = "DAP synthetic corners"


def _load_script():
    spec = importlib.util.spec_from_file_location("setup_corner_stages", SCRIPT)
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
        for code in ("Q-235", "Q-240"):
            db.add(
                StructuralComponent(
                    id=f"corner-{code}",
                    project_id="p1",
                    segment_id=segment.id,
                    type="beam",
                    raw_code=code,
                    canonical_code=code,
                    verification="NEEDS_REVIEW",
                    record_origin="MANUAL_ENTRY",
                    created_by="u1",
                )
            )
        db.commit()


def _sources(corner_csv: Path, workbook: Path) -> None:
    corner_csv.write_text(
        "page;drawing;zone;segment;group;corner_type;source_row;location_code\n"
        "104;TK-98;Cầu dẫn;7;III;01;1;Q-235\n"
        "104;TK-98;Cầu dẫn;7;III;01;2;Q-240\n",
        encoding="utf-8",
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Cầu dẫn công tác dầm"
    ws.append(
        [
            "page",
            "drawing",
            "group",
            "source_row",
            "work_item",
            "unit",
            "part_1_raw",
            "part_2_raw",
            "part_3_raw",
            "total_raw",
        ]
    )
    ws.append([111, "TK-105", "II", 1, "ignored", "m²", 1, 2, None, 3])
    rows = [
        ("Đục bê tông om vỡ dày TB 70 mm", "m³", "1,423"),
        ("Vệ sinh bề mặt kết cấu bê tông", "m²", "21,013"),
        ("Tẩy gỉ cốt thép (50% diện tích bề mặt)", "m²", "10,507"),
        ("Quét epoxy HM-180C3P hoặc tương đương, 0,8 kg/m²", "m²", "21,013"),
        ("Phủ cát tạo nhám", "m²", "21,013"),
        ("Ván khuôn", "m²", "24,371"),
        ("Vữa không co ngót tính năng cao", "m³", "1,423"),
        ("Vận chuyển đổ thải", "m³", "1,423"),
    ]
    for position, (name, unit, total) in enumerate(rows, start=1):
        ws.append([112, "TK-106", "III", position, name, unit, None, None, None, total])
    wb.save(workbook)


def _run(database: Path, corner_csv: Path, workbook: Path, *extra: str):
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
            "--corner-source",
            str(corner_csv),
            "--workbook",
            str(workbook),
            *extra,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_workbook_stages_reads_exactly_eight_group_iii_rows(tmp_path):
    module = _load_script()
    workbook = tmp_path / "book.xlsx"
    corner_csv = tmp_path / "corners.csv"
    _sources(corner_csv, workbook)
    stages = module._workbook_stages(workbook)
    assert [item["position"] for item in stages] == list(range(1, 9))
    assert stages[0]["name"] == "Đục bê tông om vỡ dày TB 70 mm"
    assert stages[0]["unit"] == "m³"
    assert stages[0]["total"] == 1.423
    assert stages[5]["name"] == "Ván khuôn"


def test_preview_commit_and_idempotent(tmp_path):
    database = tmp_path / "app.db"
    corner_csv = tmp_path / "corners.csv"
    workbook = tmp_path / "book.xlsx"
    _seed(database)
    _sources(corner_csv, workbook)

    preview = _run(database, corner_csv, workbook)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "stages to add: 16" in preview.stdout
    assert "stage definitions to create: 8" in preview.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert db.scalar(select(ComponentStage)) is None
        assert db.scalar(select(StageDefinition)) is None
        assert db.scalar(select(DesignGroup)) is None

    committed = _run(database, corner_csv, workbook, "--commit")
    assert committed.returncode == 0, committed.stdout + committed.stderr
    assert '"stages_added": 16' in committed.stdout
    assert '"definitions_created": 8' in committed.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        group = db.scalar(select(DesignGroup))
        assert group is not None
        assert group.name == "Góc dầm"
        assert group.group_type == "BEAM_REPAIR_CLASS"
        definitions = list(
            db.scalars(select(StageDefinition).order_by(StageDefinition.position)).all()
        )
        assert len(definitions) == 8
        assert [item.code for item in definitions] == [
            f"DAP-GOC-{position:02d}" for position in range(1, 9)
        ]
        components = list(db.scalars(select(StructuralComponent)).all())
        assert {item.design_group_id for item in components} == {group.id}
        stages = list(db.scalars(select(ComponentStage)).all())
        assert len(stages) == 16
        for component in components:
            own = [item for item in stages if item.component_id == component.id]
            assert len(own) == 8
            quantities = [item.design_quantity for item in own]
            assert all(item["quantity"] is None for item in quantities)
            assert all(item["scope"] == "SUBGROUP" for item in quantities)
            assert {item["unit"] for item in quantities} == {"m³", "m²"}
            assert all("XEM TỔNG CỘT PHÂN NHÓM" in item["note"] for item in quantities)
        assert db.scalar(select(AuditLog).where(AuditLog.action == "component_corner_stages_setup"))

    rerun = _run(database, corner_csv, workbook, "--commit")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert '"stages_added": 0' in rerun.stdout
    assert '"definitions_created": 0' in rerun.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert len(list(db.scalars(select(ComponentStage)).all())) == 16
