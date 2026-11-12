from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from openpyxl import Workbook
from io import BytesIO
import zipfile
from types import SimpleNamespace

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.models import AuditLog, User
from app.main import app


def test_auth_project_scope_and_work_item(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'core.db'}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(auth, "SessionLocal", factory)
    monkeypatch.setattr(access, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="admin-test", password_hash=password_hash("test-password-long"), role="admin"))
        db.commit()
    client = TestClient(app)
    assert client.get("/api/v1/projects").json()["code"] == "http_401"
    response = client.post("/api/v1/auth/login", json={"username": "admin-test", "password": "test-password-long"})
    assert response.status_code == 200
    admin = {"Authorization": f"Bearer {response.json()['access_token']}"}
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Test Project"})
    assert project.status_code == 201
    project_id = project.json()["id"]
    updated_project = client.patch(f"/api/v1/projects/{project_id}", headers=admin,
                                   json={"client": "Chủ đầu tư A", "location": "Hà Nội"})
    assert updated_project.status_code == 200
    assert updated_project.json()["client"] == "Chủ đầu tư A"
    assert client.get("/api/v1/projects", headers=admin).json()[0]["location"] == "Hà Nội"
    user = client.post("/api/v1/users", headers=admin, json={"username": "viewer-test", "password": "viewer-password-long", "role": "viewer"})
    assert user.status_code == 201
    viewer_token = client.post("/api/v1/auth/login", json={"username": "viewer-test", "password": "viewer-password-long"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {viewer_token}"}
    assert client.get(f"/api/v1/projects/{project_id}/work-items", headers=viewer).status_code == 404
    assert client.post(f"/api/v1/projects/{project_id}/members", headers=admin, params={"user_id": user.json()["id"], "role": "viewer"}).status_code == 201
    assert client.get(f"/api/v1/projects/{project_id}/work-items", headers=viewer).status_code == 200
    assert client.patch(f"/api/v1/projects/{project_id}", headers=viewer,
                        json={"client": "Không được phép"}).status_code == 403
    assert client.post(f"/api/v1/projects/{project_id}/work-items", headers=viewer, json={"code": "W1", "name": "Test item"}).status_code == 403
    assert client.post(f"/api/v1/projects/{project_id}/work-items", headers=viewer, json={"code": "W1", "name": "Test item"}).json()["code"] == "http_403"
    created_item = client.post(f"/api/v1/projects/{project_id}/work-items", headers=admin, json={"code": "W1", "name": "Test item"})
    assert created_item.status_code == 201
    assert len(client.get(f"/api/v1/projects/{project_id}/work-items", headers=viewer).json()) == 1
    changed = client.patch(f"/api/v1/projects/{project_id}/work-items/{created_item.json()['id']}", headers=admin,
                           json={"status": "in_progress"})
    assert changed.status_code == 200 and changed.json()["status"] == "in_progress"
    assert client.patch(f"/api/v1/projects/{project_id}/work-items/{created_item.json()['id']}", headers=viewer,
                        json={"status": "completed"}).status_code == 403
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "DM"
    sheet["A6"] = 2
    sheet["C6"] = "Synthetic repair task"
    sheet["D6"] = "Test component"
    content = BytesIO()
    workbook.save(content)
    preview = client.post(f"/api/v1/projects/{project_id}/work-items/import-preview", headers=admin,
                          files={"file": ("synthetic.xlsx", content.getvalue())})
    assert preview.status_code == 200
    assert preview.json()["items"][0]["code"] == "DM-2"
    imported = client.post(f"/api/v1/projects/{project_id}/work-items/import", headers=admin,
                           json={"items": preview.json()["items"]})
    assert imported.status_code == 201
    assert imported.json()[0]["name"] == "Synthetic repair task"
    organization = client.post(f"/api/v1/projects/{project_id}/organizations", headers=admin,
                               json={"name": "Nhà thầu thử nghiệm", "kind": "contractor"})
    assert organization.status_code == 201
    assert client.post(f"/api/v1/projects/{project_id}/organizations", headers=viewer,
                       json={"name": "Không được phép"}).status_code == 403
    person = client.post(f"/api/v1/projects/{project_id}/personnel", headers=admin,
                         json={"name": "Nhân sự thử nghiệm", "organization_id": organization.json()["id"]})
    assert person.status_code == 201
    assert len(client.get(f"/api/v1/projects/{project_id}/personnel", headers=viewer).json()) == 1
    second = client.post("/api/v1/projects", headers=admin, json={"name": "Second project"}).json()["id"]
    assert client.patch(f"/api/v1/projects/{second}/work-items/{created_item.json()['id']}", headers=admin,
                        json={"status": "completed"}).status_code == 404
    cross_project = client.post(f"/api/v1/projects/{second}/personnel", headers=admin,
                                json={"name": "Other", "organization_id": organization.json()["id"]})
    assert cross_project.status_code == 404

    class OversizedArchive:
        def __init__(self, _file):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def infolist(self):
            return [SimpleNamespace(file_size=101 * 1024 * 1024)]

    monkeypatch.setattr(zipfile, "ZipFile", OversizedArchive)
    oversized = client.post(f"/api/v1/projects/{project_id}/work-items/import-preview", headers=admin,
                            files={"file": ("synthetic.xlsx", content.getvalue())})
    assert oversized.status_code == 422
    assert oversized.json()["detail"] == "XLSX expands beyond 100 MB"
    assert client.post("/api/v1/auth/logout", headers=viewer).status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/work-items", headers=viewer).status_code == 401


def test_change_password_revokes_tokens_and_checks_old_password(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'password.db'}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(auth, "SessionLocal", factory)
    monkeypatch.setattr(access, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="password-user", password_hash=password_hash("old-password-123"), role="engineer"))
        db.commit()

    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "password-user", "password": "old-password-123"},
    )
    assert login.status_code == 200
    old_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    wrong = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": "wrong-password", "new_password": "new-password-456"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "Current password is incorrect"

    short = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": "old-password-123", "new_password": "short"},
    )
    assert short.status_code == 422

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": "old-password-123", "new_password": "new-password-456"},
    )
    assert changed.status_code == 200
    assert changed.json() == {"status": "password_changed", "relogin": True}

    assert client.get("/api/v1/projects", headers=old_headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "password-user", "password": "old-password-123"},
    ).status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "password-user", "password": "new-password-456"},
    )
    assert new_login.status_code == 200
    new_headers = {"Authorization": f"Bearer {new_login.json()['access_token']}"}
    assert client.get("/api/v1/projects", headers=new_headers).status_code == 200

    with factory() as db:
        logs = db.query(AuditLog).filter(AuditLog.action == "change_password").all()
        assert len(logs) == 1
        assert logs[0].actor_id
        assert "password" not in (logs[0].detail or "").lower()
