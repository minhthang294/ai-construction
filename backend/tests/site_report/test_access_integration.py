"""Integration test with the real shared auth/access helpers.

Unlike the fast API tests, this builds an app with the core router + site router,
the real bearer middleware and the real project membership checks.  Only the
database session is swapped for an in-memory SQLite database.
"""

import io

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.access as core_access
import app.core.auth as core_auth
from app.core import database as core_database
from app.core.models import (
    ApiToken,
    Project,
    ProjectMember,
    User,
    WorkItem,
)
from app.core.router import router as core_router
from app.core.auth import authenticate, password_hash, reset_current_user, set_current_user
from app.site.models import Base
from app.site.router import get_db as site_get_db
from app.site.router import router as site_router


@pytest.fixture()
def auth_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # The shared auth/access helpers resolve SessionLocal from their modules.
    monkeypatch.setattr(core_auth, "SessionLocal", Session)
    monkeypatch.setattr(core_access, "SessionLocal", Session)

    with Session() as db:
        db.add_all(
            [
                User(id="u-admin", username="admin", password_hash=password_hash("admin-pass-long"), role="admin"),
                User(id="u-eng", username="engineer", password_hash=password_hash("eng-pass-long"), role="engineer"),
                User(id="u-view", username="viewer", password_hash=password_hash("view-pass-long"), role="viewer"),
                User(id="u-out", username="outsider", password_hash=password_hash("out-pass-long"), role="viewer"),
                Project(id="proj-1", name="Project 1"),
                Project(id="proj-2", name="Project 2"),
                ProjectMember(id="m1", project_id="proj-1", user_id="u-eng", role="engineer"),
                ProjectMember(id="m2", project_id="proj-1", user_id="u-view", role="viewer"),
                WorkItem(id="wi-1", project_id="proj-1", code="W1", name="Work item"),
            ]
        )
        db.commit()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1") and path != "/api/v1/auth/login":
            value = request.headers.get("Authorization", "")
            if not value.startswith("Bearer "):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            try:
                user = authenticate(value[7:])
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            token = set_current_user(user)
            try:
                return await call_next(request)
            finally:
                reset_current_user(token)
        return await call_next(request)

    app.include_router(core_router, prefix="/api/v1")
    app.include_router(site_router, prefix="/api/v1")
    app.dependency_overrides[core_database.get_db] = override_db
    app.dependency_overrides[site_get_db] = override_db

    with TestClient(app) as client:
        yield client


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload():
    return {
        "status": "draft",
        "notes": None,
        "manpower": [{"group_name": "Workers", "count": 0}],
        "work_logs": [],
        "next_day_plans": [],
    }


def test_outside_project_gets_404_everywhere(auth_client):
    outsider = _login(auth_client, "outsider", "out-pass-long")
    assert (
        auth_client.get(
            "/api/v1/projects/proj-1/daily-reports/2026-11-11", headers=outsider
        ).status_code
        == 404
    )
    assert (
        auth_client.put(
            "/api/v1/projects/proj-1/daily-reports/2026-11-11",
            headers=outsider,
            json=_payload(),
        ).status_code
        == 404
    )
    assert (
        auth_client.get("/api/v1/projects/proj-2/daily-reports/2026-11-11", headers=outsider).status_code
        == 404
    )


def test_viewer_can_read_but_not_write(auth_client):
    viewer = _login(auth_client, "viewer", "view-pass-long")
    engineer = _login(auth_client, "engineer", "eng-pass-long")

    saved = auth_client.put(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11",
        headers=engineer,
        json=_payload(),
    )
    assert saved.status_code == 200, saved.text

    read = auth_client.get(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11", headers=viewer
    )
    assert read.status_code == 200
    assert read.json()["manpower"][0]["count"] == 0

    forbidden = auth_client.put(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11",
        headers=viewer,
        json=_payload(),
    )
    assert forbidden.status_code == 403

    photo = auth_client.post(
        "/api/v1/projects/proj-1/photos",
        headers=viewer,
        files=[("files", ("a.png", io.BytesIO(b"photo"), "image/png"))],
    )
    assert photo.status_code == 403


def test_engineer_can_upload_and_viewer_can_read_original(auth_client):
    engineer = _login(auth_client, "engineer", "eng-pass-long")
    viewer = _login(auth_client, "viewer", "view-pass-long")

    uploaded = auth_client.post(
        "/api/v1/projects/proj-1/photos",
        headers=engineer,
        files=[("files", ("a.png", io.BytesIO(b"photo-bytes"), "image/png"))],
        data={"category": "progress"},
    )
    assert uploaded.status_code == 201, uploaded.text
    photo_id = uploaded.json()[0]["id"]

    original = auth_client.get(
        f"/api/v1/projects/proj-1/photos/{photo_id}/original", headers=viewer
    )
    assert original.status_code == 200
    assert original.content == b"photo-bytes"

    outsider = _login(auth_client, "outsider", "out-pass-long")
    assert (
        auth_client.get(
            f"/api/v1/projects/proj-1/photos/{photo_id}/original", headers=outsider
        ).status_code
        == 404
    )


def test_reviewed_and_role_checks_on_export(auth_client):
    engineer = _login(auth_client, "engineer", "eng-pass-long")
    viewer = _login(auth_client, "viewer", "view-pass-long")

    auth_client.put(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11",
        headers=engineer,
        json=_payload(),
    )
    draft_export = auth_client.post(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11/exports",
        headers=engineer,
        json={"format": "zalo"},
    )
    assert draft_export.status_code == 409

    viewer_export = auth_client.post(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11/exports",
        headers=viewer,
        json={"format": "zalo"},
    )
    assert viewer_export.status_code == 403

    reviewed = _payload()
    reviewed["status"] = "reviewed"
    assert (
        auth_client.put(
            "/api/v1/projects/proj-1/daily-reports/2026-11-11",
            headers=engineer,
            json=reviewed,
        ).status_code
        == 200
    )
    ok = auth_client.post(
        "/api/v1/projects/proj-1/daily-reports/2026-11-11/exports",
        headers=engineer,
        json={"format": "zalo"},
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["auto_send"] is False
