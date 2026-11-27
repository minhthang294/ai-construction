"""Design parameter display in stage names, overview, journal and daily preview."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (
    ComponentDesignParameter,
    ComponentStage,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.design_parameters import display_stage_name
from app.core.models import User
from app.main import app

PASSWORD = "design-params-password"
STAGE_NAME = "Đục bê tông om vỡ dày trung bình t"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'design-params.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="design-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "design-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _project(client, admin, name="Design"):
    return client.post("/api/v1/projects", headers=admin, json={"name": name}).json()["id"]


def _seed(factory, project_id):
    with factory() as db:
        admin = db.scalar(select(User).where(User.username == "design-admin"))
        zone = StructureZone(project_id=project_id, name="Cầu chính", name_key="cầu chính")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
        db.add(segment)
        db.flush()
        definition = StageDefinition(project_id=project_id, component_type="pile",
                                     code="DUC", name=STAGE_NAME, position=1)
        db.add(definition)
        db.flush()
        rows = []
        for code, t_value in (("F67", 2.0), ("F64", 5.0)):
            component = StructuralComponent(
                project_id=project_id, segment_id=segment.id, type="pile",
                raw_code=code, canonical_code=code, verification="VERIFIED",
                record_origin="MANUAL_ENTRY", created_by=admin.id)
            db.add(component)
            db.flush()
            scope = RepairScope(component_id=component.id, kind="DESIGN_SCOPE",
                                verification="VERIFIED", revision=1)
            db.add(scope)
            db.flush()
            stage = ComponentStage(component_id=component.id,
                                   stage_definition_id=definition.id,
                                   repair_scope_id=scope.id, created_by=admin.id)
            db.add(stage)
            db.flush()
            db.add(ComponentDesignParameter(
                project_id=project_id, component_id=component.id, name="t_cm",
                value=t_value, unit="cm", source_drawing="TK-19", source_page=25,
                source_row=1, source_file_hash="a" * 64, created_by=admin.id,
                created_at=datetime.now(timezone.utc)))
            db.add(ProgressEvent(component_id=component.id, component_stage_id=stage.id,
                                 event_date=date(2026, 11, 22), status="COMPLETED",
                                 evidence_refs="[]", created_by=admin.id))
            rows.append((component, stage))
        db.commit()
        return rows[0][0].id, rows[0][1].id


def test_display_stage_name_formats_single_range_and_missing():
    assert display_stage_name(STAGE_NAME, [3]) == f"{STAGE_NAME[:-2]} t = 3 cm"
    assert display_stage_name(STAGE_NAME, [2, 5]) == f"{STAGE_NAME[:-2]} t = 2–5 cm"
    assert display_stage_name(STAGE_NAME, [None]) == f"{STAGE_NAME[:-2]} t (chưa có số liệu)"
    assert display_stage_name("Đục sườn", [3]) == "Đục sườn"


def test_detail_overview_daily_and_journal_use_per_pile_t(env):
    client, factory, admin = env
    project = _project(client, admin)
    component_id, stage_id = _seed(factory, project)

    detail = client.get(f"/api/v1/projects/{project}/components/{component_id}", headers=admin)
    assert detail.status_code == 200
    body = detail.json()
    assert body["design_parameters"][0]["name"] == "t_cm"
    assert body["design_parameters"][0]["value"] == 2
    assert body["stages"][0]["name"] == f"{STAGE_NAME[:-2]} t = 2 cm"

    latest = client.get(f"/api/v1/projects/{project}/overview/latest-day", headers=admin).json()
    assert latest["works"][0]["stage_name"] == "Đục bê tông"
    assert latest["works"][0]["codes"] == ["F64 (t = 5 cm)", "F67 (t = 2 cm)"]

    preview = client.post(f"/api/v1/projects/{project}/progress/daily-preview", headers=admin, json={
        "event_date": "2026-11-22",
        "lines": [{
            "stage_definition_id": body["stages"][0]["stage_definition_id"],
            "component_ids": [component_id],
            "status": "COMPLETED",
        }],
    })
    assert preview.status_code == 200, preview.text
    assert preview.json()["lines"][0]["stage_display_name"] == f"{STAGE_NAME[:-2]} t = 2 cm"

    journal = client.get(f"/api/v1/projects/{project}/journals/2026-11-22/preview",
                         headers=admin).json()
    names = [item["stage_name"] for item in journal["construction_events"]]
    assert f"{STAGE_NAME[:-2]} t = 2 cm" in names
    assert f"{STAGE_NAME[:-2]} t = 5 cm" in names
