"""Repair scope review, construction stages and append-only progress events.

Every test uses its own temporary SQLite database; data/app.db is never touched.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import AcceptanceRecord, AcceptanceRequest
from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (ComponentStage, ProgressEvent, RepairScope, Segment,
                                       StageDefinition, StructuralComponent, StructureZone)
from app.core.models import AuditLog, User
from app.main import app
from app.site.models import SitePhoto

PASSWORD = "progress-password-long"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'progress.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="progress-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "progress-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


def make_user(client, admin, username, role):
    created = client.post("/api/v1/users", headers=admin,
                          json={"username": username, "password": PASSWORD, "role": role})
    token = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    return created.json()["id"], {"Authorization": f"Bearer {token.json()['access_token']}"}


def add_member(client, admin, project, user_id, role):
    return client.post(f"/api/v1/projects/{project}/members", headers=admin,
                       params={"user_id": user_id, "role": role})


def create_project(client, admin, name):
    response = client.post("/api/v1/projects", headers=admin, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def seed_component(factory, project, code="P-01", component_type="pile"):
    with factory() as db:
        admin = db.scalar(select(User).where(User.username == "progress-admin"))
        zone = StructureZone(project_id=project, name="Khu A", name_key="khu a")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=1, source_code="S1")
        db.add(segment)
        db.flush()
        component = StructuralComponent(project_id=project, segment_id=segment.id, type=component_type,
                                        raw_code=code, canonical_code=code, verification="NEEDS_REVIEW",
                                        record_origin="MANUAL_ENTRY", created_by=admin.id)
        db.add(component)
        db.flush()
        scope = RepairScope(component_id=component.id, kind="DESIGN_SCOPE",
                            verification="NEEDS_REVIEW", revision=1)
        db.add(scope)
        db.commit()
        return component.id, scope.id


def test_repair_scope_review_is_project_scoped_and_audited(env):
    client, factory, admin = env
    project = create_project(client, admin, "Scope review")
    other_project = create_project(client, admin, "Other scope")
    component, _ = seed_component(factory, project)
    _, other_scope = seed_component(factory, other_project, "P-02")

    engineer_id, engineer = make_user(client, admin, "scope-engineer", "engineer")
    manager_id, manager = make_user(client, admin, "scope-manager", "project_manager")
    viewer_id, viewer = make_user(client, admin, "scope-viewer", "viewer")
    outsider_id, outsider = make_user(client, admin, "scope-outsider", "project_manager")
    for user_id, role in ((engineer_id, "engineer"), (manager_id, "project_manager"), (viewer_id, "viewer")):
        assert add_member(client, admin, project, user_id, role).status_code == 201
    assert add_member(client, admin, other_project, outsider_id, "project_manager").status_code == 201

    url = f"/api/v1/projects/{project}/components/{component}/repair-scopes"
    assert client.post(url, headers=viewer, json={"kind": "ADDITIONAL_SCOPE"}).status_code == 403
    first = client.post(url, headers=engineer,
                        json={"kind": "ADDITIONAL_SCOPE", "approval_reference": "PS-01"})
    assert first.status_code == 201, first.text
    assert first.json()["revision"] == 1 and first.json()["verification"] == "NEEDS_REVIEW"
    assert first.json()["reviewed_by"] is None and first.json()["reviewed_at"] is None
    second = client.post(url, headers=engineer, json={"kind": "ADDITIONAL_SCOPE"})
    assert second.status_code == 201 and second.json()["revision"] == 2
    design = client.post(url, headers=engineer, json={"kind": "DESIGN_SCOPE"})
    assert design.status_code == 201 and design.json()["revision"] == 2

    review = f"{url}/{first.json()['id']}/review"
    assert client.post(review, headers=engineer, json={"decision": "VERIFIED"}).status_code == 403
    assert client.post(review, headers=viewer, json={"decision": "VERIFIED"}).status_code == 403
    assert client.post(review, headers=outsider, json={"decision": "VERIFIED"}).status_code == 404
    assert client.post(f"{url}/{second.json()['id']}/review", headers=manager,
                       json={"decision": "VERIFIED"}).status_code == 422
    rejected = client.post(f"{url}/{second.json()['id']}/review", headers=manager,
                           json={"decision": "REJECTED", "note": "No signed approval"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["verification"] == "REJECTED" and rejected.json()["reviewed_by"] == manager_id
    verified = client.post(review, headers=manager, json={"decision": "VERIFIED"})
    assert verified.status_code == 200, verified.text
    assert verified.json()["verification"] == "VERIFIED"
    assert verified.json()["approval_reference"] == "PS-01"
    assert verified.json()["reviewed_by"] == manager_id and verified.json()["reviewed_at"] is not None
    assert client.post(review, headers=manager, json={"decision": "VERIFIED"}).status_code == 409
    assert client.post(f"{url}/{other_scope}/review", headers=manager,
                       json={"decision": "VERIFIED"}).status_code == 404
    assert client.post(f"/api/v1/projects/{other_project}/components/{component}/repair-scopes",
                       headers=admin, json={"kind": "ADDITIONAL_SCOPE"}).status_code == 404

    detail = client.get(f"/api/v1/projects/{project}/components/{component}", headers=viewer).json()
    assert {(scope["kind"], scope["revision"]): scope["verification"] for scope in detail["scopes"]} == {
        ("DESIGN_SCOPE", 1): "NEEDS_REVIEW", ("ADDITIONAL_SCOPE", 1): "VERIFIED",
        ("ADDITIONAL_SCOPE", 2): "REJECTED", ("DESIGN_SCOPE", 2): "NEEDS_REVIEW"}
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "repair_scope_proposed")) == 3
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "repair_scope_reviewed")) == 2
        stored = db.scalar(select(RepairScope).where(RepairScope.id == first.json()["id"]))
        assert stored.reviewed_at is not None and stored.reviewed_by == manager_id


def test_stages_and_progress_are_append_only_and_do_not_touch_acceptance(env):
    client, factory, admin = env
    project = create_project(client, admin, "Construction")
    other_project = create_project(client, admin, "Other construction")
    component, scope = seed_component(factory, project)
    other_component, other_scope = seed_component(factory, other_project, "P-02")
    with factory() as db:
        photo = SitePhoto(project_id=project, original_path="photo.jpg", sha256="a" * 64,
                          category="progress")
        unconfirmed = SitePhoto(project_id=project, original_path="raw.jpg", sha256="b" * 64)
        foreign_photo = SitePhoto(project_id=other_project, original_path="foreign.jpg",
                                  sha256="c" * 64, category="progress")
        db.add_all([photo, unconfirmed, foreign_photo])
        db.commit()
        photo_id, unconfirmed_id, foreign_photo_id = photo.id, unconfirmed.id, foreign_photo.id

    engineer_id, engineer = make_user(client, admin, "progress-engineer", "engineer")
    manager_id, manager = make_user(client, admin, "progress-manager", "project_manager")
    viewer_id, viewer = make_user(client, admin, "progress-viewer", "viewer")
    for user_id, role in ((engineer_id, "engineer"), (manager_id, "project_manager"), (viewer_id, "viewer")):
        add_member(client, admin, project, user_id, role)

    definitions = f"/api/v1/projects/{project}/stage-definitions"
    assert client.post(definitions, headers=viewer,
                       json={"type": "pile", "code": "SP", "name": "Surface prep"}).status_code == 403
    pile_definition = client.post(definitions, headers=engineer,
                                  json={"type": "pile", "code": " surface-prep ", "name": "Chuẩn bị bề mặt",
                                        "position": 10})
    assert pile_definition.status_code == 201, pile_definition.text
    assert pile_definition.json()["code"] == "SURFACE-PREP"
    assert client.post(definitions, headers=engineer,
                       json={"type": "pile", "code": "SURFACE-PREP", "name": "Duplicate"}).status_code == 409
    beam_definition = client.post(definitions, headers=engineer,
                                  json={"type": "beam", "code": "BEAM-1", "name": "Beam step"})
    assert beam_definition.status_code == 201
    assert len(client.get(definitions, headers=viewer).json()) == 2
    assert [item["code"] for item in client.get(definitions, headers=viewer,
                                                params={"type": "beam"}).json()] == ["BEAM-1"]
    assert client.get(f"/api/v1/projects/{other_project}/stage-definitions", headers=admin).json() == []

    stages = f"/api/v1/projects/{project}/components/{component}/stages"
    payload = {"stage_definition_id": pile_definition.json()["id"], "repair_scope_id": scope}
    assert client.post(stages, headers=viewer, json=payload).status_code == 403
    stage = client.post(stages, headers=engineer, json=payload)
    assert stage.status_code == 201, stage.text
    assert stage.json()["status"] == "NOT_STARTED" and stage.json()["code"] == "SURFACE-PREP"
    assert client.post(stages, headers=engineer, json=payload).status_code == 409
    second_scope = client.post(f"/api/v1/projects/{project}/components/{component}/repair-scopes",
                               headers=engineer, json={"kind": "ADDITIONAL_SCOPE",
                                                       "approval_reference": "PS-02"})
    assert second_scope.status_code == 201
    reused = client.post(stages, headers=engineer,
                         json={**payload, "repair_scope_id": second_scope.json()["id"]})
    assert reused.status_code == 201, reused.text
    assert reused.json()["id"] != stage.json()["id"]
    assert reused.json()["stage_definition_id"] == pile_definition.json()["id"]
    assert reused.json()["repair_scope_id"] == second_scope.json()["id"]
    assert client.post(stages, headers=engineer,
                       json={**payload, "stage_definition_id": beam_definition.json()["id"]}).status_code == 409
    assert client.post(stages, headers=engineer,
                       json={**payload, "repair_scope_id": other_scope}).status_code == 404
    other_definition = client.post(f"/api/v1/projects/{other_project}/stage-definitions", headers=admin,
                                   json={"type": "pile", "code": "OTHER", "name": "Other"}).json()
    assert client.post(stages, headers=engineer,
                       json={"stage_definition_id": other_definition["id"], "repair_scope_id": scope}).status_code == 404
    other_stage = client.post(f"/api/v1/projects/{other_project}/components/{other_component}/stages",
                              headers=admin, json={"stage_definition_id": other_definition["id"],
                                                   "repair_scope_id": other_scope})
    assert other_stage.status_code == 201
    assert client.post(f"/api/v1/projects/{other_project}/components/{component}/stages",
                       headers=admin, json=payload).status_code == 404

    events = f"/api/v1/projects/{project}/components/{component}/progress-events"
    base = {"stage_id": stage.json()["id"], "event_date": "2026-11-01", "status": "IN_PROGRESS",
            "quantity": 2.5, "unit": "m3", "note": "Bắt đầu",
            "evidence_refs": [f"photo:{photo_id}"]}
    assert client.post(events, headers=viewer, json=base).status_code == 403
    first = client.post(events, headers=engineer, json=base)
    assert first.status_code == 201, first.text
    assert first.json()["event_date"] == "2026-11-01" and first.json()["stage_id"] == stage.json()["id"]
    assert first.json()["evidence_refs"] == [f"photo:{photo_id}"]
    assert first.json()["created_by"] == engineer_id
    second = client.post(events, headers=manager,
                         json={**base, "event_date": "2026-11-02", "status": "COMPLETED"})
    assert second.status_code == 201

    assert client.post(events, headers=engineer,
                       json={**base, "event_date": None}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "quantity": -1}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "status": "DONE"}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": [""]}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": [f"photo:{foreign_photo_id}"]}).status_code == 404
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": [f"photo:{unconfirmed_id}"]}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": ["photo:missing"]}).status_code == 404
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": ["document:missing"]}).status_code == 404
    assert client.post(events, headers=engineer,
                       json={**base, "evidence_refs": ["unknown:1"]}).status_code == 422
    assert client.post(events, headers=engineer,
                       json={**base, "stage_id": "missing"}).status_code == 404
    assert client.post(events, headers=engineer,
                       json={**base, "stage_id": other_stage.json()["id"]}).status_code == 404
    assert client.delete(events, headers=engineer).status_code == 405
    assert client.patch(events, headers=engineer).status_code == 405

    listing = client.get(events, headers=viewer).json()
    assert [item["event_date"] for item in listing] == ["2026-11-01", "2026-11-02"]
    assert client.get(events, headers=viewer, params={"stage_id": "missing"}).status_code == 404
    assert len(client.get(events, headers=viewer, params={"stage_id": stage.json()["id"]}).json()) == 2
    detail = client.get(f"/api/v1/projects/{project}/components/{component}", headers=viewer).json()
    stages_by_id = {item["id"]: item for item in detail["stages"]}
    assert stages_by_id[stage.json()["id"]]["status"] == "COMPLETED"
    assert stages_by_id[reused.json()["id"]]["status"] == "NOT_STARTED"
    assert len(detail["progress_events"]) == 2
    assert "acceptance" not in detail
    assert client.get(f"/api/v1/projects/{other_project}/components/{component}/progress-events",
                      headers=admin).status_code == 404
    assert client.post(f"/api/v1/projects/{other_project}/components/{component}/progress-events",
                       headers=admin, json=base).status_code == 404

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ProgressEvent)) == 2
        assert db.scalar(select(func.count()).select_from(ComponentStage)) == 3
        assert db.scalar(select(func.count()).select_from(StageDefinition)) == 3
        assert db.scalar(select(func.count()).select_from(AcceptanceRequest)) == 0
        assert db.scalar(select(func.count()).select_from(AcceptanceRecord)) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "component_progress_recorded")) == 2
