"""End-to-end import checks on a synthetic workbook.

The workbook is generated in memory; no project data, private seed or
data/app.db is read. Every test uses its own temporary SQLite database.
"""

import base64
import hashlib
import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.component_models import (ComponentAlias, ComponentImportBatch, ComponentWorkLink,
                                       DesignGroup, RepairScope, Segment, StructuralComponent,
                                       StructureZone)
from app.core.models import AuditLog, User
from app.main import app

PASSWORD = "synthetic-password-long"
ZONE = "Khu A"
SHEET_HEADERS = {
    "DANH_MUC": ["Mã", "Khu vực", "Loại", "Phân đoạn", "Nhóm", "Mã chuẩn", "Phạm vi", "Bản vẽ", "Nguồn"],
    "LIEN_KET_CONG_VIEC": ["STT", "Mã cấu kiện", "", "Mã", "Dòng DM", "", "Công việc", "", "", "", "", "", "Vị trí"],
    "18_PHAN_DOAN": ["Mã", "Khu vực", "Số phân đoạn"],
}


def base_data():
    segments = [{"id": f"S{n}", "zone": ZONE, "number": n} for n in range(1, 19)]
    components = [
        {"id": "P1", "zone": ZONE, "kind": "Cọc", "segment": 1, "group": "Nhóm 2", "code": "P-01",
         "scope": "Danh mục gốc", "drawing": "D-01", "source": "Bản vẽ trang 8"},
        {"id": "P2", "zone": ZONE, "kind": "Cọc", "segment": 1, "group": "Nhóm 3", "code": "P-02",
         "scope": "Danh mục gốc", "drawing": "D-02", "source": "Bản vẽ trang 15"},
        {"id": "B1", "zone": ZONE, "kind": "Dầm", "segment": 1, "group": None, "code": "I-40-42",
         "scope": "Danh mục gốc", "drawing": "D-02", "source": "Bản vẽ trang 15"},
        {"id": "B2", "zone": ZONE, "kind": "Dầm", "segment": 1, "group": None, "code": "B-01",
         "scope": "Phát sinh sửa chữa", "drawing": "D-02", "source": "Bản vẽ trang 15"},
        {"id": "B3", "zone": ZONE, "kind": "Dầm", "segment": 1, "group": None, "code": "B-02",
         "scope": "Phát sinh sửa chữa", "drawing": "D-02", "source": "Bản vẽ trang 15"},
    ]
    links = [
        {"component": "P1", "code": "P-01", "dm_row": 6, "work": "Khoan cọc", "location": "Khu A / P-01"},
        {"component": "B1", "code": "I-40-42", "dm_row": 7, "work": "Sửa chữa dầm", "location": "Trụ T5 I40-42"},
        {"component": "B2", "code": "B-01", "dm_row": 8, "work": "Đục bê tông", "location": "Khu A / B-01"},
    ]
    return segments, components, links


def workbook_bytes(segments, components, links):
    workbook = Workbook()
    for title, rows in (
        ("DANH_MUC", [[c["id"], c["zone"], c["kind"], c["segment"], c["group"], c["code"],
                       c["scope"], c["drawing"], c["source"]] for c in components]),
        ("LIEN_KET_CONG_VIEC", [[1, link["component"], None, link["code"], link["dm_row"], None,
                                 link["work"], None, None, None, None, None, link["location"]]
                                for link in links]),
        ("18_PHAN_DOAN", [[s["id"], s["zone"], s["number"]] for s in segments]),
    ):
        sheet = workbook.active if title == "DANH_MUC" else workbook.create_sheet()
        sheet.title = title
        for column, value in enumerate(SHEET_HEADERS[title], 1):
            sheet.cell(1, column, value)
        for row_number, values in enumerate(rows, 5):
            for column, value in enumerate(values, 1):
                sheet.cell(row_number, column, value)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'synthetic.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="qa-admin", password_hash=password_hash(PASSWORD), role="admin"))
        db.commit()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"username": "qa-admin", "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return client, factory, headers


def create_project(client, headers, name):
    response = client.post("/api/v1/projects", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def login_as(client, headers, username, role):
    response = client.post("/api/v1/users", headers=headers,
                           json={"username": username, "password": PASSWORD, "role": role})
    assert response.status_code == 201, response.text
    token = client.post("/api/v1/auth/login",
                        json={"username": username, "password": PASSWORD}).json()["access_token"]
    return response.json()["id"], {"Authorization": f"Bearer {token}"}


def preview(client, url, headers, content):
    return client.post(url + "/import-preview", headers=headers,
                       files={"file": ("synthetic.xlsx", content)})


def commit_body(preview_json, content, key="import-1"):
    return {"reviewed": True, "idempotency_key": key, "preview": preview_json,
            "source_file_base64": base64.b64encode(content).decode()}


def counts(factory):
    with factory() as db:
        return {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                for model in (StructureZone, Segment, StructuralComponent, ComponentAlias,
                              ComponentWorkLink, RepairScope, DesignGroup, ComponentImportBatch,
                              AuditLog)}


def test_preview_is_read_only_and_rejects_invalid_upload(env):
    client, factory, headers = env
    project = create_project(client, headers, "Synthetic preview")
    url = f"/api/v1/projects/{project}/components"
    segments, components, links = base_data()
    content = workbook_bytes(segments, components, links)

    response = preview(client, url, headers, content)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_sha256"] == hashlib.sha256(content).hexdigest()
    assert body["conflicts"] == []
    assert len(body["components"]) == 5 and len(body["segments"]) == 18
    assert {c["type"] for c in body["components"]} == {"pile", "beam"}
    assert sum(c["scope"] == "ADDITIONAL_SCOPE" for c in body["components"]) == 2
    assert all(c["verification"] == "NEEDS_REVIEW" for c in body["components"])
    assert [c for c in body["components"] if c["canonical_code"] == "I-40-42"][0]["aliases"] == ["I40-42"]
    component_tables = ("structure_zones", "structure_segments", "structural_components",
                        "component_aliases", "component_work_links", "component_repair_scopes",
                        "component_design_groups", "component_import_batches")
    assert all(counts(factory)[table] == 0 for table in component_tables)

    assert preview(client, url, headers, b"not an xlsx").status_code == 422
    incomplete = Workbook()
    incomplete.active.title = "DANH_MUC"
    buffer = BytesIO()
    incomplete.save(buffer)
    assert preview(client, url, headers, buffer.getvalue()).status_code == 422

    viewer_id, viewer = login_as(client, headers, "qa-viewer", "viewer")
    client.post(f"/api/v1/projects/{project}/members", headers=headers,
                params={"user_id": viewer_id, "role": "viewer"})
    assert preview(client, url, viewer, content).status_code == 403

    _, outsider = login_as(client, headers, "qa-outsider", "engineer")
    assert preview(client, url, outsider, content).status_code == 404


def test_commit_needs_review_and_is_idempotent_and_scoped_to_segment_one(env):
    client, factory, headers = env
    project = create_project(client, headers, "Synthetic commit")
    url = f"/api/v1/projects/{project}/components"
    segments, components, links = base_data()
    content = workbook_bytes(segments, components, links)
    body_preview = preview(client, url, headers, content).json()
    body = commit_body(body_preview, content)

    assert client.post(url + "/import-commit", headers=headers,
                       json={**body, "reviewed": False}).status_code == 422
    altered = json.loads(json.dumps({**body_preview, "conflicts": []}))
    altered["components"][0]["canonical_code"] = "P-99"
    assert client.post(url + "/import-commit", headers=headers,
                       json={**body, "preview": altered}).status_code == 409
    assert client.post(url + "/import-commit", headers=headers,
                       json={**body, "source_file_base64": "eA=="}).status_code == 422
    assert counts(factory)["structural_components"] == 0

    first = client.post(url + "/import-commit", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json() == {"components": 5, "work_links": 3, "segments": 18}

    same_key = client.post(url + "/import-commit", headers=headers, json=body)
    new_key = client.post(url + "/import-commit", headers=headers, json={**body, "idempotency_key": "import-2"})
    assert same_key.json() == new_key.json() == first.json()
    assert counts(factory)["structural_components"] == 5
    assert counts(factory)["component_work_links"] == 3
    assert counts(factory)["structure_segments"] == 18
    assert counts(factory)["component_import_batches"] == 2
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "import_reviewed")) == 2

    changed = base_data()
    changed[2][0]["work"] = "Nội dung đã đổi"
    changed_content = workbook_bytes(*changed)
    changed_preview = preview(client, url, headers, changed_content).json()
    assert client.post(url + "/import-commit", headers=headers,
                       json={**body, "preview": changed_preview}).status_code == 409

    listing = client.get(url, headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 5
    assert {item["segment_number"] for item in listing.json()} == {1}
    assert listing.json() == client.get(url, headers=headers, params={"zone": " khu a "}).json()
    assert len(client.get(url, headers=headers, params={"type": "beam"}).json()) == 3
    assert len(client.get(url, headers=headers, params={"scope": "ADDITIONAL_SCOPE"}).json()) == 2
    assert [item["canonical_code"] for item in
            client.get(url, headers=headers, params={"q": "B-01"}).json()] == ["B-01"]

    alias = client.get(url, headers=headers, params={"q": "I40-42"}).json()
    canonical = client.get(url, headers=headers, params={"q": "I-40-42"}).json()
    assert len(alias) == 1 and alias == canonical
    assert alias[0]["raw_code"] == "I40-42" and "I40-42" in alias[0]["aliases"]
    detail = client.get(f"{url}/{alias[0]['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["source"]["sheet"] == "DANH_MUC"
    assert detail.json()["design_group"] is None
    assert [scope["kind"] for scope in detail.json()["scopes"]] == ["DESIGN_SCOPE"]
    assert detail.json()["work_links"][0]["dm_row"] == 7
    pile = client.get(url, headers=headers, params={"q": "P-01"}).json()[0]
    pile_detail = client.get(f"{url}/{pile['id']}", headers=headers).json()
    assert pile_detail["design_group"]["name"] == "Nhóm 2"
    assert pile_detail["design_group"]["source_page"] == 8
    additional = client.get(url, headers=headers, params={"q": "B-01"}).json()[0]
    additional_detail = client.get(f"{url}/{additional['id']}", headers=headers).json()
    assert additional_detail["design_group"] is None

    segment_rows = client.get(f"/api/v1/projects/{project}/segments", headers=headers).json()
    assert [row["number"] for row in segment_rows] == list(range(1, 19))
    for row in segment_rows[1:]:
        assert client.get(url, headers=headers, params={"segment_id": row["id"]}).json() == []
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(StructuralComponent)) == 5
        assert {group.source_page for group in db.scalars(select(DesignGroup))} == {8, 15}
        assert db.scalar(select(StructuralComponent.verification)) == "VERIFIED"
        assert db.scalar(select(StructuralComponent.record_origin)) == "SEED_IMPORT"
        assert db.scalar(select(StructuralComponent.created_by)) is not None
        assert db.scalar(select(RepairScope.revision)) == 1
        assert db.scalar(select(AuditLog.action).where(
            AuditLog.action == "import_reviewed")) == "import_reviewed"


def test_changed_source_alias_and_invalid_workbook_require_manual_review(env):
    client, factory, headers = env
    project = create_project(client, headers, "Synthetic conflicts")
    url = f"/api/v1/projects/{project}/components"
    content = workbook_bytes(*base_data())
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(preview(client, url, headers, content).json(), content)).status_code == 200

    changed = base_data()
    changed[2][0]["work"] = "Nội dung đã đổi"
    changed_content = workbook_bytes(*changed)
    changed_preview = preview(client, url, headers, changed_content)
    assert changed_preview.status_code == 200
    assert "Existing component requires manual reconciliation" in changed_preview.json()["conflicts"]
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(changed_preview.json(), changed_content, "changed")).status_code == 409

    alias_collision = base_data()
    alias_collision[1].append({"id": "B4", "zone": ZONE, "kind": "Dầm", "segment": 1, "group": None,
                               "code": "I40-42", "scope": "Danh mục gốc", "drawing": "D-02",
                               "source": "Bản vẽ trang 15"})
    alias_content = workbook_bytes(*alias_collision)
    alias_preview = preview(client, url, headers, alias_content)
    assert alias_preview.status_code == 200
    assert "Ambiguous component alias" in alias_preview.json()["conflicts"]
    assert "Existing component requires manual reconciliation" in alias_preview.json()["conflicts"]
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(alias_preview.json(), alias_content, "alias")).status_code == 409

    duplicate = base_data()
    duplicate[1].append({**duplicate[1][0]})
    duplicate[2].append({**duplicate[2][0]})
    duplicate_content = workbook_bytes(*duplicate)
    duplicate_preview = preview(client, url, headers, duplicate_content)
    assert "Duplicate segment, component, source ID or work link" in duplicate_preview.json()["conflicts"]
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(duplicate_preview.json(), duplicate_content, "dup")).status_code == 409

    unknown = base_data()
    unknown[2].append({"component": "MISSING", "code": "P-01", "dm_row": 9, "work": "Mồ côi",
                       "location": "Không tồn tại"})
    unknown_content = workbook_bytes(*unknown)
    unknown_preview = preview(client, url, headers, unknown_content)
    assert "Unknown segment or component reference" in unknown_preview.json()["conflicts"]
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(unknown_preview.json(), unknown_content, "unknown")).status_code == 409

    mismatched_link = base_data()
    mismatched_link[2][0]["code"] = "P-02"
    mismatched_content = workbook_bytes(*mismatched_link)
    mismatched_preview = preview(client, url, headers, mismatched_content)
    assert "Work link code does not match component" in mismatched_preview.json()["conflicts"]
    assert client.post(url + "/import-commit", headers=headers,
                       json=commit_body(mismatched_preview.json(), mismatched_content, "link")).status_code == 409

    assert counts(factory)["structural_components"] == 5
    assert counts(factory)["component_import_batches"] == 1


def test_project_roles_and_isolation_apply_to_import(env):
    client, factory, headers = env
    project = create_project(client, headers, "Synthetic roles")
    other_project = create_project(client, headers, "Synthetic other")
    url = f"/api/v1/projects/{project}/components"
    other_url = f"/api/v1/projects/{other_project}/components"
    data = base_data()
    content = workbook_bytes(*data)

    viewer_id, viewer = login_as(client, headers, "qa-viewer-2", "viewer")
    client.post(f"/api/v1/projects/{project}/members", headers=headers,
                params={"user_id": viewer_id, "role": "viewer"})
    engineer_id, engineer = login_as(client, headers, "qa-engineer", "engineer")
    client.post(f"/api/v1/projects/{project}/members", headers=headers,
                params={"user_id": engineer_id, "role": "engineer"})

    assert client.get(url, headers=viewer).status_code == 200
    assert preview(client, url, viewer, content).status_code == 403
    assert client.post(url + "/import-commit", headers=viewer,
                       json=commit_body(preview(client, url, headers, content).json(), content)).status_code == 403
    assert client.get(other_url, headers=viewer).status_code == 404

    engineer_preview = preview(client, url, engineer, content)
    assert engineer_preview.status_code == 200
    committed = client.post(url + "/import-commit", headers=engineer,
                            json=commit_body(engineer_preview.json(), content))
    assert committed.status_code == 200, committed.text
    with factory() as db:
        assert {component.created_by for component in db.scalars(select(StructuralComponent))} == {engineer_id}

    assert preview(client, other_url, engineer, content).status_code == 404
    assert client.get(other_url, headers=headers).json() == []
    assert client.get(f"/api/v1/projects/{other_project}/segments", headers=headers).json() == []
    component_id = client.get(url, headers=headers).json()[0]["id"]
    assert client.get(f"{other_url}/{component_id}", headers=headers).status_code == 404
    assert client.get(url, headers=headers).json() == client.get(url, headers=headers, params={"q": ""}).json()

    import_preview = preview(client, other_url, headers, content)
    assert import_preview.status_code == 200
    assert client.post(other_url + "/import-commit", headers=headers,
                       json=commit_body(import_preview.json(), content, "other")).status_code == 200
    assert len(client.get(other_url, headers=headers).json()) == 5
    assert len(client.get(url, headers=headers).json()) == 5
    assert counts(factory)["structural_components"] == 10
