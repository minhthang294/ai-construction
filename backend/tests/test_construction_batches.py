"""Construction batches: scope, code preview/ambiguity, audit and filters."""

from datetime import date, datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (ComponentStage, ProgressEvent, RepairScope, Segment,
                                       StageDefinition, StructuralComponent, StructureZone)
from app.core.models import AuditLog, User
from app.main import app

PASSWORD = "batch-password-long"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'batches.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="batch-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "batch-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


class Seed:
    def __init__(self, db, project: str):
        self.db = db
        self.project = project
        self.admin = db.scalar(select(User).where(User.username == "batch-admin"))
        self.zone_a = StructureZone(project_id=project, name="Khu A", name_key="khu a")
        self.zone_b = StructureZone(project_id=project, name="Khu B", name_key="khu b")
        db.add_all([self.zone_a, self.zone_b])
        db.flush()
        self.seg_a = Segment(zone_id=self.zone_a.id, number=1, source_code="A1")
        self.seg_b = Segment(zone_id=self.zone_b.id, number=1, source_code="B1")
        db.add_all([self.seg_a, self.seg_b])
        db.flush()
        self.definition = StageDefinition(project_id=project, component_type="pile",
                                          code="SP", name="Surface prep", position=1)
        db.add(self.definition)
        db.flush()

    def component(self, code: str, segment: Segment):
        component = StructuralComponent(
            project_id=self.project, segment_id=segment.id, type="pile",
            raw_code=code, canonical_code=code, verification="VERIFIED",
            record_origin="MANUAL_ENTRY", created_by=self.admin.id)
        self.db.add(component)
        self.db.flush()
        scope = RepairScope(component_id=component.id, kind="DESIGN_SCOPE",
                            verification="VERIFIED", revision=1)
        self.db.add(scope)
        self.db.flush()
        stage = ComponentStage(component_id=component.id,
                               stage_definition_id=self.definition.id,
                               repair_scope_id=scope.id, created_by=self.admin.id)
        self.db.add(stage)
        self.db.flush()
        return component, stage

    def event(self, component, stage, day: str):
        self.db.add(ProgressEvent(component_id=component.id, component_stage_id=stage.id,
                                  event_date=date.fromisoformat(day), status="COMPLETED",
                                  evidence_refs="[]", created_by=self.admin.id))
        self.db.flush()


def _project(client, admin, name="Batches"):
    return client.post("/api/v1/projects", headers=admin, json={"name": name}).json()["id"]


def _member(client, admin, project, username, role):
    user_id = client.post("/api/v1/users", headers=admin,
                          json={"username": username, "password": PASSWORD, "role": "viewer"}).json()["id"]
    client.post(f"/api/v1/projects/{project}/members", headers=admin,
                params={"user_id": user_id, "role": role})
    token = client.post("/api/v1/auth/login",
                        json={"username": username, "password": PASSWORD}).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_preview_separates_matched_ambiguous_and_missing_and_never_picks(env):
    client, factory, admin = env
    project = _project(client, admin)
    with factory() as db:
        seed = Seed(db, project)
        unique, _ = seed.component("A1", seed.seg_a)
        first, _ = seed.component("DUP", seed.seg_a)
        second, _ = seed.component("DUP", seed.seg_b)
        db.commit()

    created = client.post(f"/api/v1/projects/{project}/construction-batches", headers=admin,
                          json={"name": "PD2 đợt 1", "note": "Cùng giàn giáo"})
    assert created.status_code == 201, created.text
    batch = created.json()
    assert batch["component_count"] == 0

    preview = client.post(
        f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components/preview",
        headers=admin, json={"codes": ["a1", "dup", "ZZZ"]})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert [item["code"] for item in body["matched"]] == ["A1"]
    assert body["matched"][0]["component"]["id"] == unique.id
    assert body["missing"] == ["ZZZ"]
    assert len(body["ambiguous"]) == 1
    assert body["ambiguous"][0]["code"] == "DUP"
    assert {item["id"] for item in body["ambiguous"][0]["candidates"]} == {first.id, second.id}

    # Adding requires explicit ids: no component was auto-picked by preview.
    added = client.post(
        f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components",
        headers=admin,
        json={"component_ids": [unique.id, first.id], "reason": "Thi công cùng đợt"},
    )
    assert added.status_code == 201, added.text
    assert added.json() == {"batch_id": batch["id"], "added": 2, "skipped": 0}

    detail = client.get(f"/api/v1/projects/{project}/construction-batches/{batch['id']}",
                        headers=admin).json()
    assert detail["component_count"] == 2
    assert detail["primary_zone"] in {"Khu A", "Khu B"}
    assert sorted(item["canonical_code"] for item in detail["components"]) == ["A1", "DUP"]

    with factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog))]
        assert "construction_batch_created" in actions
        assert actions.count("construction_batch_component_added") == 2


def test_batch_scope_read_write_and_filters(env, tmp_path, monkeypatch):
    client, factory, admin = env
    project = _project(client, admin, "Filtered")
    other = _project(client, admin, "Other")
    with factory() as db:
        seed = Seed(db, project)
        in_batch, stage = seed.component("A1", seed.seg_a)
        outside, outside_stage = seed.component("B1", seed.seg_b)
        seed.event(in_batch, stage, "2026-11-20")
        seed.event(outside, outside_stage, "2026-11-25")
        other_seed = Seed(db, other)
        other_seed.component("X1", other_seed.seg_a)
        db.commit()
    batch = client.post(f"/api/v1/projects/{project}/construction-batches", headers=admin,
                        json={"name": "Chỉ A1"}).json()
    client.post(f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components",
                headers=admin, json={"component_ids": [in_batch.id]})

    _, engineer = _member(client, admin, project, "batch-engineer", "engineer")
    _, viewer = _member(client, admin, project, "batch-viewer", "viewer")
    assert client.get(f"/api/v1/projects/{project}/construction-batches",
                      headers=viewer).status_code == 200
    assert client.post(f"/api/v1/projects/{project}/construction-batches", headers=viewer,
                       json={"name": "No"}).status_code == 403
    assert client.get(f"/api/v1/projects/{other}/construction-batches",
                      headers=viewer).status_code == 404

    components = client.get(f"/api/v1/projects/{project}/components?batch_id={batch['id']}",
                            headers=viewer).json()
    assert [item["id"] for item in components] == [in_batch.id]
    summary = client.get(f"/api/v1/projects/{project}/progress/summary?batch_id={batch['id']}",
                         headers=viewer).json()
    assert summary["components"]["verified"] == 1
    assert summary["construction"]["completed"] == 1
    segments = client.get(f"/api/v1/projects/{project}/overview/segments?batch_id={batch['id']}",
                          headers=viewer).json()["segments"]
    assert [(item["zone"], item["segment"], item["verified_components"]) for item in segments] == [
        ("Khu A", 1, 1)]
    latest = client.get(f"/api/v1/projects/{project}/overview/latest-day?batch_id={batch['id']}",
                        headers=viewer).json()
    assert latest["date"] == "2026-11-20"
    assert [work["codes"] for work in latest["works"]] == [["A1"]]

    # Drawing map is filtered to the batch as well.
    from app.core import drawing_map_router
    map_root = tmp_path / "maps"
    (map_root / "pd2").mkdir(parents=True)
    (map_root / "pd2" / "sheet.jpg").write_bytes(b"fake")
    (map_root / "pd2" / "manifest.json").write_text(json.dumps({
        "project_id": project,
        "sheets": [{
            "id": "pd2-1", "title": "PD2", "drawing": "D", "page": 1, "image": "sheet.jpg",
            "markers": [
                {"code": "A1", "type": "pile", "points": [[0.1, 0.1]], "zone": "Khu A", "segment": 1},
                {"code": "B1", "type": "pile", "points": [[0.2, 0.2]], "zone": "Khu B", "segment": 1},
            ],
        }],
        "review": [],
    }), encoding="utf-8")
    monkeypatch.setattr(drawing_map_router, "MAP_ROOT", map_root)
    drawing = client.get(f"/api/v1/projects/{project}/drawing-map?batch_id={batch['id']}",
                         headers=viewer).json()
    assert [marker["code"] for marker in drawing["sheets"][0]["markers"]] == ["A1"]


def test_remove_component_is_audited(env):
    client, factory, admin = env
    project = _project(client, admin, "Remove")
    with factory() as db:
        seed = Seed(db, project)
        component, _ = seed.component("A1", seed.seg_a)
        db.commit()
    batch = client.post(f"/api/v1/projects/{project}/construction-batches", headers=admin,
                        json={"name": "Remove me"}).json()
    client.post(f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components",
                headers=admin, json={"component_ids": [component.id]})
    removed = client.delete(
        f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components/{component.id}"
        "?reason=Wrong+scope", headers=admin)
    assert removed.status_code == 200
    with factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog))]
        assert "construction_batch_component_removed" in actions
