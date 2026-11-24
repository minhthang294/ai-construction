"""Synthetic tests for scripts/fix_alias_f3639.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.acceptance.models import (
    AcceptanceRecord,
    AcceptanceRequest,
    ComponentAcceptanceLink,
)
from app.core.component_models import (
    ComponentAlias,
    ComponentStage,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.database import Base
from app.core.models import AuditLog, Project, ProjectMember, User

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "fix_alias_f3639.py"
PROJECT_NAME = "DAP synthetic PD1"
WORK = "Đục bê tông om vỡ"


def _database_url(path: Path) -> str:
    return "sqlite:///" + path.as_posix()


def _seed(database: Path, *, conflicting_alias: bool = False) -> None:
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
            component_type="beam",
            code="DUC",
            name="Đục bê tông om vỡ dày trung bình t",
            position=0,
        )
        db.add(definition)
        db.flush()
        component = StructuralComponent(
            id="beam-1",
            project_id="p1",
            segment_id=segment.id,
            type="beam",
            raw_code="I-36-39",
            canonical_code="I-36-39",
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
        db.add(
            ComponentStage(
                component_id=component.id,
                stage_definition_id=definition.id,
                repair_scope_id=scope.id,
                created_by="u1",
            )
        )
        if conflicting_alias:
            other = StructuralComponent(
                id="beam-2",
                project_id="p1",
                segment_id=segment.id,
                type="beam",
                raw_code="I-99-99",
                canonical_code="I-99-99",
                verification="verified",
                created_by="u1",
            )
            db.add(other)
            db.flush()
            db.add(
                ComponentAlias(
                    project_id="p1",
                    segment_id=segment.id,
                    type="beam",
                    alias="F-36-39",
                    component_id=other.id,
                )
            )
        request = AcceptanceRequest(
            id="req-46",
            project_id="p1",
            number="YC-41",
            status="draft",
            subject=WORK,
            content=WORK,
            request_date=None,
            field="construction",
            urgency="normal",
            notes=(
                "[import_acceptance_workbook] sheet=DM; row=46; number=41; "
                "segment=1; source=synthetic.xlsx\nmã chưa khớp: F-36-39"
            ),
        )
        db.add(request)
        db.flush()
        db.add(
            AcceptanceRecord(
                id="rec-46",
                project_id="p1",
                request_id=request.id,
                number="NT-41",
                revision=1,
                status="draft",
                other_notes=request.notes,
            )
        )
        db.commit()


def _run(database: Path, *extra: str) -> subprocess.CompletedProcess[str]:
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
            *extra,
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_preview_commit_links_draft_and_is_idempotent(tmp_path):
    database = tmp_path / "app.db"
    _seed(database)

    preview = _run(database)
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "Alias F-36-39 -> I-36-39: missing" in preview.stdout
    assert "Row 46 (YC-41): 1 link(s) to add" in preview.stdout
    assert "Rows without imported draft: 47, 48, 49, 50" in preview.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert db.scalar(select(ComponentAlias)) is None
        assert db.scalar(select(ComponentAcceptanceLink)) is None

    committed = _run(database, "--commit")
    assert committed.returncode == 0, committed.stdout + committed.stderr
    assert '"alias_created": true' in committed.stdout
    assert '"links_added": 1' in committed.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        alias = db.scalar(select(ComponentAlias))
        assert alias is not None
        assert alias.alias == "F-36-39"
        assert alias.component_id == "beam-1"
        link = db.scalar(select(ComponentAcceptanceLink))
        assert link is not None
        assert link.component_id == "beam-1"
        assert link.record_id == "rec-46"
        assert link.stage_id is not None
        assert link.scope_id is not None
        assert db.get(AcceptanceRequest, "req-46").status == "draft"
        assert db.get(AcceptanceRecord, "rec-46").status == "draft"
        assert db.scalar(
            select(AuditLog).where(AuditLog.action == "acceptance_alias_fix_applied")
        )

    rerun = _run(database, "--commit")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert '"alias_created": false' in rerun.stdout
    assert '"links_added": 0' in rerun.stdout
    with Session(create_engine(_database_url(database), future=True)) as db:
        assert len(list(db.scalars(select(ComponentAlias)).all())) == 1
        assert len(list(db.scalars(select(ComponentAcceptanceLink)).all())) == 1


def test_conflicting_alias_aborts_without_writes(tmp_path):
    database = tmp_path / "app.db"
    _seed(database, conflicting_alias=True)

    result = _run(database, "--commit")
    assert result.returncode == 2
    assert "already points to" in result.stdout + result.stderr
    with Session(create_engine(_database_url(database), future=True)) as db:
        alias = db.scalar(select(ComponentAlias))
        assert alias.component_id == "beam-2"
        assert db.scalar(select(ComponentAcceptanceLink)) is None
