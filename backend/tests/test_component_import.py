from pathlib import Path
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.models import AuditLog, User
from app.core.component_models import (ComponentAlias, DesignGroup, RepairScope, Segment,
                                       StructuralComponent, ComponentWorkLink, StructureZone)
from app.main import app


def test_reviewed_seed_import_is_project_scoped_and_idempotent(tmp_path, monkeypatch):
    seed = Path(__file__).resolve().parents[2] / "Danh_muc_coc_dam_Phan_doan1_va_khung_18_phan_doan.xlsx"
    if not seed.exists():
        pytest.skip("private seed not available")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="admin-import", password_hash=password_hash("test-password-long"), role="admin"))
        db.commit()
    client = TestClient(app)
    token = client.post("/api/v1/auth/login", json={"username": "admin-import", "password": "test-password-long"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Synthetic"}).json()["id"]
    url = f"/api/v1/projects/{project}/components"
    preview = client.post(url + "/import-preview", headers=headers, files={"file": ("seed.xlsx", seed.read_bytes())})
    assert preview.status_code == 200, preview.text
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(StructuralComponent)) == 0
    body = {"reviewed": True, "idempotency_key": "seed-1", "preview": preview.json(),
            "source_file_base64": b64encode(seed.read_bytes()).decode()}
    first = client.post(url + "/import-commit", headers=headers, json=body)
    assert first.status_code == 200, first.text
    second = client.post(url + "/import-commit", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert client.post(url + "/import-commit", headers=headers, json={**body, "idempotency_key": "seed-2"}).status_code == 200
    altered = preview.json()
    altered["work_links"][0]["work"] = "Changed after import"
    assert client.post(url + "/import-commit", headers=headers, json={**body, "idempotency_key": "changed", "preview": altered}).status_code == 409
    assert client.post(url + "/import-commit", headers=headers, json={**body, "idempotency_key": "bad-source", "source_file_base64": "eA=="}).status_code == 422
    assert len(client.get(url, headers=headers).json()) == 130
    assert len(client.get(url, headers=headers, params={"type": "beam", "zone": " CẦU CHÍNH "}).json()) == 20
    assert client.get(url, headers=headers, params={"zone": "Cầu dẫn"}).json() == []
    assert len(client.get(f"/api/v1/projects/{project}/segments", headers=headers).json()) == 18
    piles = client.get(url, headers=headers, params={"type": "pile"}).json()
    assert len(piles) == 110
    assert sum(item["design_group"] == "Nhóm 2" for item in piles) == 45
    assert sum(item["design_group"] == "Nhóm 3" for item in piles) == 39
    additional = client.get(url, headers=headers, params={"scope": "ADDITIONAL_SCOPE"}).json()
    assert len(additional) == 34
    assert sum(item["type"] == "pile" for item in additional) == 26
    assert sum(item["type"] == "beam" for item in additional) == 8
    assert all(item["design_group"] is None for item in additional)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(StructuralComponent)) == 130
        assert db.scalar(select(func.count()).select_from(ComponentWorkLink)) == 949
        link = db.scalar(select(ComponentWorkLink).where(ComponentWorkLink.dm_row == 6))
        assert link.seed_row >= 5 and link.seed_sheet == "LIEN_KET_CONG_VIEC"
        assert {group.source_page for group in db.scalars(select(DesignGroup))} == {8, 15}
        assert db.scalar(select(StructuralComponent.created_by)) is not None
        assert db.scalar(select(RepairScope.revision)) == 1
        imported_scopes = db.scalars(select(RepairScope)).all()
        assert imported_scopes and all(scope.verification == "VERIFIED" and scope.reviewed_by is not None
                                       and scope.reviewed_at is not None for scope in imported_scopes)
        target = db.scalar(select(StructuralComponent).where(StructuralComponent.canonical_code == "I-40-42"))
        scope = db.scalar(select(RepairScope).where(RepairScope.component_id == target.id))
        db.add(RepairScope(component_id=target.id, kind=scope.kind, verification="NEEDS_REVIEW",
                           revision=2, reviewed_by=scope.reviewed_by))
        db.flush()
        db.rollback()
        other = db.scalar(select(StructuralComponent).where(StructuralComponent.type == "beam", StructuralComponent.id != target.id))
        db.add(ComponentAlias(component_id=other.id, project_id=project, segment_id=other.segment_id,
                              type=other.type, alias="I40-42"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    assert client.post(url + "/import-commit", headers=headers, json={**body, "reviewed": False}).status_code == 422
    canonical = client.get(url, headers=headers, params={"q": "I-40-42"}).json()
    alias = client.get(url, headers=headers, params={"q": "I40-42"}).json()
    assert len(canonical) == 1 and alias == canonical
    assert canonical[0]["raw_code"] == "I40-42"
    assert canonical[0]["segment_number"] == 1 and "I40-42" in canonical[0]["aliases"]
    detail = client.get(f"{url}/{canonical[0]['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["source"]["sheet"] == "DANH_MUC"
    assert any("I40-42" in link["raw_location"] for link in detail.json()["work_links"])
    viewer_id = client.post("/api/v1/users", headers=headers, json={"username": "viewer-import", "password": "test-password-long", "role": "viewer"}).json()["id"]
    client.post(f"/api/v1/projects/{project}/members", headers=headers, params={"user_id": viewer_id, "role": "viewer"})
    viewer_token = client.post("/api/v1/auth/login", json={"username": "viewer-import", "password": "test-password-long"}).json()["access_token"]
    viewer = {"Authorization": f"Bearer {viewer_token}"}
    assert client.get(url, headers=viewer).status_code == 200
    assert client.post(url + "/import-commit", headers=viewer, json=body).status_code == 403
    other_project = client.post("/api/v1/projects", headers=headers, json={"name": "Another"}).json()["id"]
    assert client.get(f"/api/v1/projects/{other_project}/components", headers=viewer).status_code == 404
    assert client.get(f"/api/v1/projects/{other_project}/components/{canonical[0]['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/projects/{other_project}/components", headers=headers).json() == []
    assert client.get(f"/api/v1/projects/{other_project}/segments", headers=headers).json() == []
    engineer_id = client.post("/api/v1/users", headers=headers, json={"username": "engineer-import", "password": "test-password-long", "role": "engineer"}).json()["id"]
    client.post(f"/api/v1/projects/{other_project}/members", headers=headers, params={"user_id": engineer_id, "role": "engineer"})
    engineer_token = client.post("/api/v1/auth/login", json={"username": "engineer-import", "password": "test-password-long"}).json()["access_token"]
    engineer = {"Authorization": f"Bearer {engineer_token}"}
    assert client.post(f"/api/v1/projects/{other_project}/components/import-commit", headers=engineer, json=body).status_code == 200
    other_segments = client.get(f"/api/v1/projects/{other_project}/segments", headers=engineer).json()
    manual = client.post(f"/api/v1/projects/{other_project}/components", headers=engineer,
                         json={"segment_id": other_segments[1]["id"], "type": "pile", "raw_code": "X1",
                               "canonical_code": "X1", "scope": "ADDITIONAL_SCOPE"})
    assert manual.status_code == 201, manual.text
    assert manual.json()["verification"] == "NEEDS_REVIEW"
    assert client.post(f"/api/v1/projects/{project}/components", headers=headers,
                       json={"segment_id": other_segments[1]["id"], "type": "pile", "raw_code": "X1",
                             "canonical_code": "X1", "scope": "ADDITIONAL_SCOPE"}).status_code == 404
    concurrent_project = client.post("/api/v1/projects", headers=headers, json={"name": "Concurrent"}).json()["id"]
    concurrent_url = f"/api/v1/projects/{concurrent_project}/components/import-commit"
    barrier = Barrier(2)

    def submit():
        barrier.wait()
        return client.post(concurrent_url, headers=headers, json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: submit(), range(2))) == [200, 200]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(StructuralComponent).where(
            StructuralComponent.project_id == concurrent_project)) == 130


def test_manual_component_stays_unverified_and_rejects_duplicate_identifiers(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'manual.db'}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as db:
        db.add(User(username="admin-manual", password_hash=password_hash("test-password-long"), role="admin"))
        db.commit()
    client = TestClient(app)
    token = client.post("/api/v1/auth/login", json={"username": "admin-manual", "password": "test-password-long"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Manual"}).json()["id"]
    other = client.post("/api/v1/projects", headers=headers, json={"name": "Other"}).json()["id"]
    with factory() as db:
        zone = StructureZone(project_id=project, name="Zone", name_key="zone")
        foreign_zone = StructureZone(project_id=other, name="Other", name_key="other")
        db.add_all([zone, foreign_zone])
        db.flush()
        segment = Segment(zone_id=zone.id, number=1, source_code="S1")
        foreign_segment = Segment(zone_id=foreign_zone.id, number=1, source_code="S1")
        db.add_all([segment, foreign_segment])
        db.commit()
        segment_id, foreign_segment_id = segment.id, foreign_segment.id
    for username, role in (("engineer-manual", "engineer"), ("viewer-manual", "viewer")):
        user_id = client.post("/api/v1/users", headers=headers,
                              json={"username": username, "password": "test-password-long", "role": role}).json()["id"]
        client.post(f"/api/v1/projects/{project}/members", headers=headers, params={"user_id": user_id, "role": role})
    engineer_token = client.post("/api/v1/auth/login", json={"username": "engineer-manual", "password": "test-password-long"}).json()["access_token"]
    viewer_token = client.post("/api/v1/auth/login", json={"username": "viewer-manual", "password": "test-password-long"}).json()["access_token"]
    engineer = {"Authorization": f"Bearer {engineer_token}"}
    viewer = {"Authorization": f"Bearer {viewer_token}"}
    url = f"/api/v1/projects/{project}/components"
    body = {"segment_id": segment_id, "type": "pile", "raw_code": "x-1", "canonical_code": "X-1",
            "scope": "ADDITIONAL_SCOPE", "aliases": ["X1"]}
    assert client.post(url, headers=viewer, json=body).status_code == 403
    assert client.post(url, headers=engineer, json={**body, "segment_id": foreign_segment_id}).status_code == 404
    created = client.post(url, headers=engineer, json=body)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["verification"] == "NEEDS_REVIEW" and data["record_origin"] == "MANUAL_ENTRY"
    assert data["raw_code"] == "x-1" and data["canonical_code"] == "X-1" and data["aliases"] == ["X1"]
    assert data["source"] == {"sha256": None, "sheet": None, "row": None}
    assert client.post(url, headers=engineer, json={**body, "canonical_code": "X-1",
                                                    "aliases": []}).status_code == 409
    assert client.post(url, headers=engineer, json={**body, "canonical_code": "X-2", "raw_code": "X-2",
                                                    "aliases": ["X1"]}).status_code == 409
    assert client.post(url, headers=engineer, json={**body, "canonical_code": "X-2", "raw_code": "x-1",
                                                    "aliases": []}).status_code == 409
    conflicting = {**body, "canonical_code": "X-9", "raw_code": "X-9", "aliases": []}
    barrier = Barrier(2)

    def submit_manual():
        barrier.wait()
        return client.post(url, headers=engineer, json=conflicting).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: submit_manual(), range(2))) == [201, 409]
    with factory() as db:
        component = db.scalar(select(StructuralComponent).where(StructuralComponent.id == data["id"]))
        assert component.source_id is None and component.source_hash is None and component.source_row is None
        scope = db.scalar(select(RepairScope).where(RepairScope.component_id == component.id))
        assert scope.verification == "NEEDS_REVIEW" and scope.reviewed_by is None
        assert scope.reviewed_at is None and scope.approval_reference is None
        assert db.scalar(select(AuditLog).where(AuditLog.action == "component_created",
                                                AuditLog.entity_id == component.id)) is not None
    detail = client.get(f"{url}/{data['id']}", headers=engineer)
    assert detail.status_code == 200 and detail.json()["source"]["sha256"] is None
