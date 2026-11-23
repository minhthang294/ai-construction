"""Voiding a progress batch and correcting a single event."""

from datetime import date, datetime, timedelta, timezone

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
from app.site.models import SiteProgressBulkBatch

PASSWORD = "void-password-long"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'void.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="void-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "void-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _project(client, admin, name="Void"):
    return client.post("/api/v1/projects", headers=admin, json={"name": name}).json()["id"]


def _member(client, admin, project, username, role):
    user_id = client.post("/api/v1/users", headers=admin,
                          json={"username": username, "password": PASSWORD, "role": "viewer"}).json()["id"]
    client.post(f"/api/v1/projects/{project}/members", headers=admin,
                params={"user_id": user_id, "role": role})
    token = client.post("/api/v1/auth/login",
                        json={"username": username, "password": PASSWORD}).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


class Seed:
    def __init__(self, db, project: str):
        self.db = db
        self.project = project
        self.admin = db.scalar(select(User).where(User.username == "void-admin"))
        self.zone = StructureZone(project_id=project, name="Cầu chính", name_key="cầu chính")
        db.add(self.zone)
        db.flush()
        self.segment = Segment(zone_id=self.zone.id, number=2, source_code="P2")
        db.add(self.segment)
        db.flush()
        self.definition = StageDefinition(project_id=project, component_type="pile",
                                          code="DUC", name="Đục bê tông om vỡ", position=1)
        db.add(self.definition)
        db.flush()
        component = StructuralComponent(
            project_id=project, segment_id=self.segment.id, type="pile",
            raw_code="F67", canonical_code="F67", verification="VERIFIED",
            record_origin="MANUAL_ENTRY", created_by=self.admin.id)
        db.add(component)
        db.flush()
        scope = RepairScope(component_id=component.id, kind="DESIGN_SCOPE",
                            verification="VERIFIED", revision=1)
        db.add(scope)
        db.flush()
        self.stage = ComponentStage(component_id=component.id,
                                    stage_definition_id=self.definition.id,
                                    repair_scope_id=scope.id, created_by=self.admin.id)
        db.add(self.stage)
        db.flush()
        self.component = component


def _bulk(client, project, headers, seed, status, key, day):
    response = client.post(f"/api/v1/projects/{project}/progress/bulk", headers=headers, json={
        "stage_definition_id": seed.definition.id,
        "component_ids": [seed.component.id],
        "event_date": day,
        "status": status,
        "reviewed": True,
        "idempotency_key": key,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_creator_or_manager_can_undo_same_day_and_voided_events_disappear(env):
    client, factory, admin = env
    project = _project(client, admin)
    with factory() as db:
        seed = Seed(db, project)
        db.commit()
    _, engineer = _member(client, admin, project, "undo-engineer", "engineer")
    _, viewer = _member(client, admin, project, "undo-viewer", "viewer")
    _, manager = _member(client, admin, project, "undo-manager", "project_manager")
    today = date.today().isoformat()

    created = _bulk(client, project, engineer, seed, "COMPLETED", "undo-1", today)
    batch_id = created["events"][0]["batch_id"]
    assert batch_id

    assert client.post(f"/api/v1/projects/{project}/progress/batches/{batch_id}/undo",
                       headers=viewer, json={"reason": "Sai"}).status_code == 403
    undone = client.post(f"/api/v1/projects/{project}/progress/batches/{batch_id}/undo",
                         headers=manager, json={"reason": "Ghi nhầm đợt"})
    assert undone.status_code == 200, undone.text
    assert undone.json()["voided"] == 1

    summary = client.get(f"/api/v1/projects/{project}/progress/summary", headers=admin).json()
    assert summary["construction"]["completed"] == 0
    assert summary["construction"]["not_started"] == 1
    segments = client.get(f"/api/v1/projects/{project}/overview/segments", headers=admin).json()
    assert segments["segments"][0]["construction"]["completed"] == 0
    latest = client.get(f"/api/v1/projects/{project}/overview/latest-day", headers=admin).json()
    assert latest["date"] is None and latest["works"] == []
    journal = client.get(f"/api/v1/projects/{project}/journals/{today}/preview", headers=admin).json()
    assert journal["construction_events"] == []

    assert client.post(f"/api/v1/projects/{project}/progress/batches/{batch_id}/undo",
                       headers=manager, json={"reason": "Lần 2"}).status_code == 409

    # Same-day rule: a batch created yesterday can no longer be undone.
    second = _bulk(client, project, engineer, seed, "COMPLETED", "undo-2", today)
    second_batch = second["events"][0]["batch_id"]
    with factory() as db:
        batch = db.get(SiteProgressBulkBatch, second_batch)
        batch.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    assert client.post(f"/api/v1/projects/{project}/progress/batches/{second_batch}/undo",
                       headers=manager, json={"reason": "Muộn"}).status_code == 409

    with factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog))]
        assert "component_progress_batch_voided" in actions


def test_correct_event_voids_old_creates_new_and_is_audited(env):
    client, factory, admin = env
    project = _project(client, admin)
    with factory() as db:
        seed = Seed(db, project)
        db.commit()
    _, engineer = _member(client, admin, project, "correct-engineer", "engineer")
    _, other_engineer = _member(client, admin, project, "other-engineer", "engineer")
    today = date.today().isoformat()

    created = _bulk(client, project, engineer, seed, "COMPLETED", "correct-1", today)
    event_id = created["events"][0]["id"]

    assert client.post(f"/api/v1/projects/{project}/progress/events/{event_id}/correct",
                       headers=other_engineer,
                       json={"status": "IN_PROGRESS", "reason": "Không phải của tôi"}).status_code == 403
    assert client.post(f"/api/v1/projects/{project}/progress/events/{event_id}/correct",
                       headers=engineer,
                       json={"status": "IN_PROGRESS", "reason": ""}).status_code == 422
    assert client.post(f"/api/v1/projects/{project}/progress/events/{event_id}/correct",
                       headers=engineer,
                       json={"status": "COMPLETED", "reason": "Trùng"}).status_code == 409

    corrected = client.post(f"/api/v1/projects/{project}/progress/events/{event_id}/correct",
                            headers=engineer,
                            json={"status": "IN_PROGRESS", "reason": "Thực tế còn làm"})
    assert corrected.status_code == 200, corrected.text
    replacement = corrected.json()
    assert replacement["status"] == "IN_PROGRESS"
    assert replacement["id"] != event_id
    assert replacement["batch_id"] is None

    with factory() as db:
        old = db.get(ProgressEvent, event_id)
        assert old.voided_at is not None
        assert old.void_reason == "Thực tế còn làm"
        actions = [row.action for row in db.scalars(select(AuditLog))]
        assert "component_progress_event_voided" in actions
        assert "component_progress_event_corrected" in actions

    history = client.get(
        f"/api/v1/projects/{project}/components/{seed.component.id}/progress-events",
        headers=admin).json()
    assert [item["id"] for item in history] == [replacement["id"]]
    summary = client.get(f"/api/v1/projects/{project}/progress/summary", headers=admin).json()
    assert summary["construction"]["completed"] == 0
    assert summary["construction"]["in_progress"] == 1
    journal = client.get(f"/api/v1/projects/{project}/journals/{today}/preview", headers=admin).json()
    assert [item["event_id"] for item in journal["construction_events"]] == [replacement["id"]]
