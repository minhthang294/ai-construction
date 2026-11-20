"""Progress summary and reconciliation on a temporary SQLite database."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import AcceptanceRecord, AcceptanceRequest, ComponentAcceptanceLink
from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (ComponentAlias, ComponentStage, ProgressEvent, RepairScope,
                                       Segment, StageDefinition, StructuralComponent, StructureZone)
from app.core.models import User
from app.main import app

PASSWORD = "insights-password-long"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'insights.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="insights-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "insights-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


class Seed:
    def __init__(self, db, project: str):
        self.db = db
        self.project = project
        admin = db.scalar(select(User).where(User.username == "insights-admin"))
        self.admin = admin
        self.zone = StructureZone(project_id=project, name="Khu A", name_key="khu a")
        db.add(self.zone)
        db.flush()
        self.segments = {}
        for number in (1, 2):
            segment = Segment(zone_id=self.zone.id, number=number, source_code=f"S{number}")
            db.add(segment)
            self.segments[number] = segment
        db.flush()
        self.definition = StageDefinition(project_id=project, component_type="pile",
                                          code="SP", name="Surface prep", position=1)
        db.add(self.definition)
        db.flush()
        self.count = 0

    def component(self, code: str, *, segment: int = 1, verification: str = "VERIFIED",
                  origin: str = "MANUAL_ENTRY", source: bool = False, scope: str = "DESIGN_SCOPE",
                  aliases: tuple[str, ...] = ()):
        component = StructuralComponent(
            project_id=self.project, segment_id=self.segments[segment].id, type="pile",
            raw_code=code, canonical_code=code, verification=verification, record_origin=origin,
            source_id="src" if source else None, source_hash="a" * 64 if source else None,
            source_row=5 if source else None, created_by=self.admin.id)
        self.db.add(component)
        self.db.flush()
        repair_scope = RepairScope(component_id=component.id, kind=scope,
                                   verification="VERIFIED", revision=self.count + 1)
        self.db.add(repair_scope)
        for alias in (code, *aliases):
            self.db.add(ComponentAlias(component_id=component.id, project_id=self.project,
                                       segment_id=component.segment_id, type="pile", alias=alias))
        self.db.flush()
        return component, repair_scope

    def stage(self, component, repair_scope):
        stage = ComponentStage(component_id=component.id, stage_definition_id=self.definition.id,
                               repair_scope_id=repair_scope.id, created_by=self.admin.id)
        self.db.add(stage)
        self.db.flush()
        return stage

    def event(self, component, stage, day: str, status: str):
        self.db.add(ProgressEvent(component_id=component.id, component_stage_id=stage.id,
                                  event_date=date.fromisoformat(day), status=status,
                                  evidence_refs="[]", created_by=self.admin.id))
        self.db.flush()

    def accepted(self, component, confirmed_at: datetime):
        self.count += 1
        request = AcceptanceRequest(project_id=self.project, number=f"YC-{self.count}")
        self.db.add(request)
        self.db.flush()
        record = AcceptanceRecord(project_id=self.project, request_id=request.id,
                                  number=f"BB-{self.count}", status="confirmed", result="approved",
                                  confirmed_at=confirmed_at)
        self.db.add(record)
        self.db.flush()
        self.db.add(ComponentAcceptanceLink(project_id=self.project, component_id=component.id,
                                           record_id=record.id, created_by=self.admin.id))
        self.db.flush()
        return record


def test_summary_counts_only_verified_components_and_keeps_statuses_separate(env):
    client, factory, admin = env
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Insights"}).json()["id"]
    with factory() as db:
        seed = Seed(db, project)
        done, done_scope = seed.component("DONE")
        seed.event(done, seed.stage(done, done_scope), "2026-11-01", "COMPLETED")
        seed.accepted(done, datetime(2026, 11, 10, tzinfo=timezone.utc))

        accepted_no_work, _ = seed.component("ACC-NO-WORK")
        seed.accepted(accepted_no_work, datetime(2026, 11, 10, tzinfo=timezone.utc))

        work, work_scope = seed.component("WORK", scope="ADDITIONAL_SCOPE")
        seed.event(work, seed.stage(work, work_scope), "2026-11-02", "COMPLETED")

        seed.component("NO-SOURCE", origin="SEED_IMPORT")
        seed.component("UNVERIFIED", verification="NEEDS_REVIEW")
        late, late_scope = seed.component("LATE")
        seed.event(late, seed.stage(late, late_scope), "2026-11-15", "IN_PROGRESS")
        seed.accepted(late, datetime(2026, 11, 10, tzinfo=timezone.utc))

        seed.component("AMB-1", segment=1, aliases=("DUP",))
        seed.component("AMB-2", segment=2, aliases=("DUP",))
        db.commit()

    response = client.get(f"/api/v1/projects/{project}/progress/summary", headers=admin)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["components"] == {"total": 8, "verified": 7, "needs_review": 1,
                                     "with_additional_scope": 1}
    assert summary["construction"] == {"not_started": 4, "in_progress": 1, "completed": 2,
                                       "blocked": 0, "completion_ratio": 0.2857}
    assert summary["acceptance"] == {"linked": 3, "confirmed": 3, "completion_ratio": 0.4286}

    issues = client.get(f"/api/v1/projects/{project}/reconciliation/issues", headers=admin)
    assert issues.status_code == 200, issues.text
    assert issues.json()["counts"] == {
        "ACCEPTANCE_WITHOUT_PROGRESS": 1, "WORK_WITHOUT_ACCEPTANCE": 1, "MISSING_SOURCE": 1,
        "UNVERIFIED_COMPONENT": 1, "DUPLICATE_OR_AMBIGUOUS_CODE": 2,
        "ACCEPTANCE_BEFORE_PROGRESS": 1}
    flagged = {(item["type"], item["canonical_code"]) for item in issues.json()["issues"]}
    assert ("ACCEPTANCE_WITHOUT_PROGRESS", "ACC-NO-WORK") in flagged
    assert ("WORK_WITHOUT_ACCEPTANCE", "WORK") in flagged
    assert ("MISSING_SOURCE", "NO-SOURCE") in flagged
    assert ("UNVERIFIED_COMPONENT", "UNVERIFIED") in flagged
    assert ("ACCEPTANCE_BEFORE_PROGRESS", "LATE") in flagged
    assert ("DUPLICATE_OR_AMBIGUOUS_CODE", "AMB-1") in flagged
    assert ("DUPLICATE_OR_AMBIGUOUS_CODE", "AMB-2") in flagged
    assert ("WORK_WITHOUT_ACCEPTANCE", "DONE") not in flagged
    assert ("ACCEPTANCE_WITHOUT_PROGRESS", "DONE") not in flagged


def test_summary_and_reconciliation_are_project_scoped_and_member_readable(env):
    client, factory, admin = env
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Scoped"}).json()["id"]
    other = client.post("/api/v1/projects", headers=admin, json={"name": "Other"}).json()["id"]
    with factory() as db:
        seed = Seed(db, project)
        seed.component("A")
        other_seed = Seed(db, other)
        confirmed, _ = other_seed.component("B")
        other_seed.accepted(confirmed, datetime(2026, 11, 10, tzinfo=timezone.utc))
        db.commit()

    assert client.get(f"/api/v1/projects/{project}/progress/summary", headers=admin).json()[
        "components"]["total"] == 1
    assert client.get(f"/api/v1/projects/{other}/reconciliation/issues", headers=admin).json()[
        "counts"]["ACCEPTANCE_WITHOUT_PROGRESS"] == 1

    viewer_id = client.post("/api/v1/users", headers=admin,
                            json={"username": "insights-viewer", "password": PASSWORD,
                                  "role": "viewer"}).json()["id"]
    client.post(f"/api/v1/projects/{project}/members", headers=admin,
                params={"user_id": viewer_id, "role": "viewer"})
    token = client.post("/api/v1/auth/login",
                        json={"username": "insights-viewer", "password": PASSWORD}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/projects/{project}/progress/summary", headers=viewer).status_code == 200
    assert client.get(f"/api/v1/projects/{project}/reconciliation/issues", headers=viewer).status_code == 200
    assert client.get(f"/api/v1/projects/{other}/progress/summary", headers=viewer).status_code == 404
