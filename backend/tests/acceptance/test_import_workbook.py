"""Synthetic tests for scripts/import_acceptance_workbook.py."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.acceptance.models import (
    AcceptanceRecord,
    AcceptanceRequest,
    ComponentAcceptanceLink,
)
from app.acceptance.pending import pending_acceptance
from app.core.component_models import (
    ComponentStage,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.database import Base
from app.core.models import AuditLog, Project, ProjectMember, User

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "import_acceptance_workbook.py"
PROJECT_NAME = "DAP synthetic PD1"


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
        segment = Segment(zone_id=zone.id, number=1, source_code="PD1")
        db.add(segment)
        definition = StageDefinition(
            project_id="p1",
            component_type="pile",
            code="DUC",
            name="Đục bê tông om vỡ dày trung bình t",
            position=0,
        )
        db.add(definition)
        db.flush()
        for index, code in enumerate(("A2", "A5")):
            component = StructuralComponent(
                id=f"c{index}",
                project_id="p1",
                segment_id=segment.id,
                type="pile",
                raw_code=code,
                canonical_code=code,
                verification="verified",
                created_by="u1",
            )
            db.add(component)
            db.flush()
            scope = RepairScope(
                component_id=component.id,
                kind="DESIGN_SCOPE",
                verification="VERIFIED",
                revision=1,
            )
            db.add(scope)
            db.flush()
            stage = ComponentStage(
                component_id=component.id,
                stage_definition_id=definition.id,
                repair_scope_id=scope.id,
                created_by="u1",
            )
            db.add(stage)
            db.flush()
            db.add(
                ProgressEvent(
                    component_id=component.id,
                    component_stage_id=stage.id,
                    event_date=date(2026, 10, 5),
                    status="COMPLETED",
                    created_by="u1",
                )
            )
        db.commit()


def _workbook(path: Path, rows: list[list[object]]) -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "DM"
    sheet.cell(1, 1, "DANH MỤC HỒ SƠ")
    sheet.cell(5, 1, "STT")
    for offset, values in enumerate(rows, start=6):
        for column, value in enumerate(values, start=1):
            sheet.cell(offset, column, value)
    workbook.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(database: Path, xlsx: Path, *extra: str) -> tuple[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--database",
            _database_url(database),
            "--project",
            PROJECT_NAME,
            "--xlsx",
            str(xlsx),
            "--segment",
            "1",
            *extra,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout, result.stderr


def _row(number, work, target, yc, nt, end, location):
    return [0, number, work, target, yc, None, nt, "16h00", end, location]


def test_preview_commit_synthetic_and_idempotent(tmp_path):
    database = tmp_path / "app.db"
    _seed(database)
    xlsx = tmp_path / "synthetic.xlsx"
    original_hash = _workbook(
        xlsx,
        [
            _row(
                "01",
                "Đục bê tông om vỡ",
                "Cọc A2, A5",
                date(2026, 10, 1),
                date(2026, 10, 2),
                "17h00",
                "Phân đoạn 1 - Cầu chính",
            ),
            _row(
                "02",
                "Đục bê tông om vỡ",
                "Cọc A2",
                date(2026, 10, 3),
                None,
                None,
                "Phân đoạn 1 - Cầu chính",
            ),
            _row(
                "03",
                "Đục bê tông om vỡ",
                "Cọc A2",
                date(2026, 10, 4),
                date(2026, 10, 5),
                "17h00",
                "Phân đoạn 2 - Cầu chính",
            ),
            _row(
                "04",
                "Đục bê tông om vỡ",
                "Cọc Z999",
                date(2026, 10, 5),
                date(2026, 10, 6),
                "17h00",
                "Phân đoạn 1 - Cầu chính",
            ),
        ],
    )

    preview, _ = _run(database, xlsx)
    assert "PYC found: 3" in preview
    assert "Confirmed: 1; needs review: 2" in preview
    assert "Rows skipped (not PD1): 1" in preview
    assert "Unmatched codes: 1" in preview
    assert "Z999" in preview
    assert "Component-stage links: 3" in preview
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert db.scalar(select(AcceptanceRequest)) is None  # preview writes nothing

    committed, _ = _run(database, xlsx, "--commit")
    assert '"pyc_created": 3' in committed
    assert '"bbnt_created": 3' in committed
    assert '"confirmed": 1' in committed
    assert '"links_created": 3' in committed

    engine = create_engine(_database_url(database), future=True)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as db:
        requests = list(db.scalars(select(AcceptanceRequest)).all())
        records = list(db.scalars(select(AcceptanceRecord)).all())
        links = list(db.scalars(select(ComponentAcceptanceLink)).all())
        assert {item.number for item in requests} == {"YC-01", "YC-02", "YC-04"}
        assert [item.number for item in records if item.status == "confirmed"] == ["NT-01"]
        assert len(links) == 3
        assert any("row=6" in (item.notes or "") for item in requests)
        assert db.scalar(
            select(AuditLog).where(AuditLog.action == "acceptance_workbook_imported")
        )
        assert pending_acceptance(db, "p1").total_components == 0

    rerun, _ = _run(database, xlsx, "--commit")
    assert '"pyc_created": 0' in rerun
    assert '"existing": 3' in rerun
    with factory() as db:
        assert len(list(db.scalars(select(AcceptanceRequest)).all())) == 3
        assert len(list(db.scalars(select(ComponentAcceptanceLink)).all())) == 3
    assert hashlib.sha256(xlsx.read_bytes()).hexdigest() == original_hash


def test_duplicate_number_keeps_first_row_as_draft(tmp_path):
    database = tmp_path / "app.db"
    _seed(database)
    xlsx = tmp_path / "duplicate.xlsx"
    _workbook(
        xlsx,
        [
            _row(
                "01",
                "Đục bê tông om vỡ",
                "Cọc A2",
                date(2026, 10, 1),
                date(2026, 10, 2),
                "17h00",
                "Phân đoạn 1 - Cầu chính",
            ),
            _row(
                "01",
                "Đục bê tông om vỡ",
                "Cọc A5",
                date(2026, 10, 2),
                date(2026, 10, 3),
                "17h00",
                "Phân đoạn 1 - Cầu chính",
            ),
        ],
    )
    preview, _ = _run(database, xlsx)
    assert "Confirmed: 0; needs review: 2" in preview
    assert "Duplicate numbers: 1" in preview
    committed, _ = _run(database, xlsx, "--commit")
    assert '"pyc_created": 1' in committed
    assert '"bbnt_created": 1' in committed
    assert '"confirmed": 0' in committed
    with Session(create_engine(_database_url(database), future=True)) as db:
        requests = list(db.scalars(select(AcceptanceRequest)).all())
        assert len(requests) == 1
        assert "số biên bản trùng" in (requests[0].notes or "")
