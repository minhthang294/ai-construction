"""Latest-day and per-segment overview on a temporary SQLite database."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import AcceptanceRecord, AcceptanceRequest, ComponentAcceptanceLink
from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (ComponentDesignParameter, ComponentStage, ProgressEvent,
                                       RepairScope, Segment, StageDefinition,
                                       StructuralComponent, StructureZone)
from app.core.models import User
from app.main import app
from app.site.models import DailyReport, ManpowerEntry, SitePhoto

PASSWORD = "overview-password-long"


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'overview.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="overview-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "overview-admin", "password": PASSWORD})
    return client, factory, {"Authorization": f"Bearer {login.json()['access_token']}"}


class Seed:
    def __init__(self, db, project: str, zone_name: str = "Khu A"):
        self.db = db
        self.project = project
        self.admin = db.scalar(select(User).where(User.username == "overview-admin"))
        self.zone = StructureZone(project_id=project, name=zone_name, name_key=zone_name.casefold())
        db.add(self.zone)
        db.flush()
        self.segments = {}
        for number in (1, 2):
            segment = Segment(zone_id=self.zone.id, number=number, source_code=f"S{number}")
            db.add(segment)
            self.segments[number] = segment
        db.flush()
        self.definition = StageDefinition(project_id=project, component_type="pile",
                                          code="DUC", name="Đục bê tông om vỡ", position=1)
        db.add(self.definition)
        db.flush()
        self.count = 0

    def component(self, code: str, *, segment: int = 1, verification: str = "VERIFIED"):
        component = StructuralComponent(
            project_id=self.project, segment_id=self.segments[segment].id, type="pile",
            raw_code=code, canonical_code=code, verification=verification,
            record_origin="MANUAL_ENTRY", created_by=self.admin.id)
        self.db.add(component)
        self.db.flush()
        scope = RepairScope(component_id=component.id, kind="DESIGN_SCOPE",
                            verification="VERIFIED", revision=1)
        self.db.add(scope)
        self.db.flush()
        return component, scope

    def stage(self, component, scope):
        stage = ComponentStage(component_id=component.id,
                               stage_definition_id=self.definition.id,
                               repair_scope_id=scope.id, created_by=self.admin.id)
        self.db.add(stage)
        self.db.flush()
        return stage

    def event(self, component, stage, day: str, status: str):
        event = ProgressEvent(component_id=component.id, component_stage_id=stage.id,
                              event_date=date.fromisoformat(day), status=status,
                              evidence_refs="[]", created_by=self.admin.id)
        self.db.add(event)
        self.db.flush()
        return event

    def report(self, day: str, manpower: list[int | None]):
        report = DailyReport(project_id=self.project, report_date=date.fromisoformat(day))
        self.db.add(report)
        self.db.flush()
        for count in manpower:
            self.db.add(ManpowerEntry(report_id=report.id, project_id=self.project,
                                      group_name="Tổ", count=count))
        self.db.flush()
        return report

    def accepted(self, component, confirmed_at: datetime, *, status: str = "confirmed"):
        self.count += 1
        request = AcceptanceRequest(project_id=self.project, number=f"YC-{self.count}")
        self.db.add(request)
        self.db.flush()
        record = AcceptanceRecord(project_id=self.project, request_id=request.id,
                                  number=f"BB-{self.count}", status=status,
                                  result="approved" if status == "confirmed" else None,
                                  confirmed_at=confirmed_at if status == "confirmed" else None)
        self.db.add(record)
        self.db.flush()
        self.db.add(ComponentAcceptanceLink(project_id=self.project,
                                           component_id=component.id,
                                           record_id=record.id,
                                           created_by=self.admin.id))
        self.db.flush()
        return record


def _project(client, admin, name="Overview"):
    return client.post("/api/v1/projects", headers=admin, json={"name": name}).json()["id"]


def test_latest_day_picks_the_max_progress_date_and_groups_works(env):
    client, factory, admin = env
    project = _project(client, admin)
    with factory() as db:
        seed = Seed(db, project, "Cầu chính")
        early, early_scope = seed.component("C1", segment=1)
        seed.event(early, seed.stage(early, early_scope), "2026-11-01", "IN_PROGRESS")
        first, first_scope = seed.component("C2", segment=2)
        seed.event(first, seed.stage(first, first_scope), "2026-11-03", "COMPLETED")
        second, second_scope = seed.component("C3", segment=2)
        seed.event(second, seed.stage(second, second_scope), "2026-11-03", "COMPLETED")
        seed.report("2026-11-02", [])
        db.commit()

    response = client.get(f"/api/v1/projects/{project}/overview/latest-day", headers=admin)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date"] == "2026-11-03"
    assert body["works"] == [{
        "stage_name": "Đục bê tông om vỡ",
        "zone": "Cầu chính",
        "segment": 2,
        "component_type": "pile",
        "status": "COMPLETED",
        "count": 2,
        "codes": ["C2", "C3"],
    }]
    assert body["manpower_total"] is None
    assert body["photo_count"] == 0
    assert body["daily_report_exists"] is False
    assert body["acceptance_today"] == []


def test_latest_day_uses_the_later_of_progress_and_daily_report(env):
    client, factory, admin = env
    project = _project(client, admin, "Later report")
    with factory() as db:
        seed = Seed(db, project)
        component, scope = seed.component("C1")
        seed.event(component, seed.stage(component, scope), "2026-11-02", "COMPLETED")
        seed.report("2026-11-07", [3])
        db.commit()

    body = client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=admin).json()
    assert body["date"] == "2026-11-07"
    assert body["works"] == []
    assert body["daily_report_exists"] is True
    assert body["manpower_total"] == 3


def test_latest_day_report_only_date_keeps_real_manpower_photos_and_acceptance(env):
    client, factory, admin = env
    project = _project(client, admin, "Report only")
    with factory() as db:
        seed = Seed(db, project)
        component, _ = seed.component("C1")
        seed.report("2026-11-05", [0, 5, None])
        db.add(SitePhoto(project_id=project, original_path="a.jpg", sha256="a" * 64,
                         upload_time=datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)))
        db.add(SitePhoto(project_id=project, original_path="b.jpg", sha256="b" * 64,
                         upload_time=datetime(2026, 11, 4, 2, 0, tzinfo=timezone.utc)))
        seed.accepted(component, datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc))
        seed.accepted(component, datetime(2026, 11, 5, 4, 0, tzinfo=timezone.utc),
                      status="draft")
        db.commit()

    body = client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=admin).json()
    assert body["date"] == "2026-11-05"
    assert body["works"] == []
    assert body["manpower_total"] == 5
    assert body["photo_count"] == 1
    assert body["daily_report_exists"] is True
    assert len(body["acceptance_today"]) == 1
    assert body["acceptance_today"][0]["component_codes"] == ["C1"]
    assert body["acceptance_today"][0]["result"] == "approved"


def test_latest_day_never_infers_acceptance_from_completed_progress(env):
    client, factory, admin = env
    project = _project(client, admin, "No fake acceptance")
    with factory() as db:
        seed = Seed(db, project)
        component, scope = seed.component("C1")
        seed.event(component, seed.stage(component, scope), "2026-11-06", "COMPLETED")
        db.commit()

    body = client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=admin).json()
    assert body["date"] == "2026-11-06"
    assert body["works"][0]["status"] == "COMPLETED"
    assert body["acceptance_today"] == []


def test_latest_day_is_project_scoped_and_member_readable(env):
    client, factory, admin = env
    project = _project(client, admin, "Scoped")
    other = _project(client, admin, "Other")
    with factory() as db:
        seed = Seed(db, project)
        component, scope = seed.component("A")
        seed.event(component, seed.stage(component, scope), "2026-11-04", "COMPLETED")
        other_seed = Seed(db, other, "Khu B")
        later, later_scope = other_seed.component("B")
        other_seed.event(later, other_seed.stage(later, later_scope), "2026-11-09", "COMPLETED")
        db.commit()

    body = client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=admin).json()
    assert body["date"] == "2026-11-04"
    assert body["works"][0]["codes"] == ["A"]

    viewer_id = client.post("/api/v1/users", headers=admin,
                            json={"username": "overview-viewer", "password": PASSWORD,
                                  "role": "viewer"}).json()["id"]
    client.post(f"/api/v1/projects/{project}/members", headers=admin,
                params={"user_id": viewer_id, "role": "viewer"})
    token = client.post("/api/v1/auth/login",
                        json={"username": "overview-viewer", "password": PASSWORD}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=viewer).status_code == 200
    assert client.get(f"/api/v1/projects/{other}/overview/latest-day",
                      headers=viewer).status_code == 404


def test_latest_day_empty_project_returns_nulls_and_empty_lists(env):
    client, _, admin = env
    project = _project(client, admin, "Empty")
    body = client.get(f"/api/v1/projects/{project}/overview/latest-day",
                      headers=admin).json()
    assert body == {"date": None, "works": [], "manpower_total": None,
                    "photo_count": 0, "daily_report_exists": False,
                    "acceptance_today": []}


def test_segments_report_construction_and_acceptance_independently(env):
    client, factory, admin = env
    project = _project(client, admin, "Segments")
    other = _project(client, admin, "Segments other")
    with factory() as db:
        seed = Seed(db, project, "Cầu chính")
        accepted_done, accepted_done_scope = seed.component("A", segment=1)
        seed.event(accepted_done, seed.stage(accepted_done, accepted_done_scope),
                   "2026-11-02", "COMPLETED")
        seed.accepted(accepted_done, datetime(2026, 11, 3, tzinfo=timezone.utc))

        done, done_scope = seed.component("B", segment=1)
        seed.event(done, seed.stage(done, done_scope), "2026-11-02", "COMPLETED")

        in_progress, in_progress_scope = seed.component("C", segment=1)
        seed.event(in_progress, seed.stage(in_progress, in_progress_scope),
                   "2026-11-02", "IN_PROGRESS")
        seed.accepted(in_progress, datetime(2026, 11, 3, tzinfo=timezone.utc))

        seed.component("D", segment=2)
        seed.component("UNVERIFIED", segment=2, verification="NEEDS_REVIEW")

        other_seed = Seed(db, other, "Khu B")
        other_seed.component("X")
        db.commit()

    body = client.get(f"/api/v1/projects/{project}/overview/segments",
                      headers=admin).json()
    segments = body["segments"]
    assert [item["segment"] for item in segments] == [1, 2]
    first, second = segments
    assert first["zone"] == "Cầu chính"
    assert first["component_count"] == 3
    assert first["verified_components"] == 3
    assert first["construction"] == {"not_started": 0, "in_progress": 1,
                                     "completed": 2, "blocked": 0,
                                     "completion_ratio": 0.6667}
    assert first["acceptance"] == {"confirmed": 2, "completion_ratio": 0.6667}
    assert second["component_count"] == 2
    assert second["verified_components"] == 1
    assert second["construction"] == {"not_started": 1, "in_progress": 0,
                                      "completed": 0, "blocked": 0,
                                      "completion_ratio": 0.0}
    assert second["acceptance"] == {"confirmed": 0, "completion_ratio": 0.0}


def test_in_progress_groups_latest_non_voided_events_by_stage_and_segment(env):
    client, factory, admin = env
    project = _project(client, admin, "In progress")
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

    def day_ago(days: int) -> str:
        return date.fromordinal(today.toordinal() - days).isoformat()

    with factory() as db:
        seed = Seed(db, project, "Cầu chính")
        seed.definition.name = "Đục bê tông om vỡ dày trung bình t"
        first, first_scope = seed.component("A1", segment=1)
        second, second_scope = seed.component("A2", segment=1)
        blocked, blocked_scope = seed.component("B1", segment=2)
        finished, finished_scope = seed.component("B2", segment=2)
        reverted, reverted_scope = seed.component("B3", segment=2)
        for component, value in ((first, 3.0), (second, 5.0)):
            db.add(ComponentDesignParameter(
                project_id=project, component_id=component.id, name="t_cm",
                value=value, unit="cm", created_by=seed.admin.id))
        seed.event(first, seed.stage(first, first_scope), day_ago(3), "IN_PROGRESS")
        seed.event(second, seed.stage(second, second_scope), day_ago(1), "IN_PROGRESS")
        seed.event(blocked, seed.stage(blocked, blocked_scope), day_ago(7), "BLOCKED")
        seed.event(finished, seed.stage(finished, finished_scope), day_ago(1), "COMPLETED")
        reverted_stage = seed.stage(reverted, reverted_scope)
        seed.event(reverted, reverted_stage, day_ago(6), "IN_PROGRESS")
        voided = seed.event(reverted, reverted_stage, day_ago(2), "COMPLETED")
        voided.voided_at = datetime.now(timezone.utc)
        db.commit()

    batch = client.post(f"/api/v1/projects/{project}/construction-batches", headers=admin,
                        json={"name": "Current"}).json()
    client.post(f"/api/v1/projects/{project}/construction-batches/{batch['id']}/components",
                headers=admin,
                json={"component_ids": [first.id, second.id, blocked.id, finished.id]})

    body = client.get(
        f"/api/v1/projects/{project}/overview/in-progress?batch_id={batch['id']}",
        headers=admin,
    ).json()
    assert body["total_components"] == 3
    assert [group["segment"] for group in body["groups"]] == [1, 2]
    assert body["groups"][0]["stage_name"].endswith("t = 3–5 cm")
    assert body["groups"][0]["component_count"] == 2
    assert body["groups"][0]["days_since_update"] == 3
    assert [item["code"] for item in body["groups"][0]["components"]] == ["A1", "A2"]
    assert body["groups"][0]["components"][1]["days_since_update"] == 1
    assert body["groups"][1]["component_count"] == 1
    assert body["groups"][1]["components"][0]["status"] == "BLOCKED"

    reverted_body = client.get(
        f"/api/v1/projects/{project}/overview/in-progress",
        headers=admin,
    ).json()
    reverted_group = next(
        group for group in reverted_body["groups"]
        if any(item["id"] == reverted.id for item in group["components"])
    )
    reverted_item = next(
        item for item in reverted_group["components"] if item["id"] == reverted.id
    )
    assert reverted_item["status"] == "IN_PROGRESS"
    assert reverted_item["days_since_update"] == 6

    other = _project(client, admin, "Other")
    foreign = client.get(
        f"/api/v1/projects/{other}/overview/in-progress?batch_id={batch['id']}",
        headers=admin,
    )
    assert foreign.status_code == 200
    assert foreign.json()["total_components"] == 0
