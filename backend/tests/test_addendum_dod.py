"""End-to-end evidence for the addendum Definition of Done.

This is a coordinator-owned integration test. It uses a temporary database and
storage, never ``data/app.db`` or the user's source workbook.
"""
from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.models import User
from app.main import app
from app.site import service as site_service




def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dod-admin", "password": "long-test-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'app.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(site_service, "STORAGE_ROOT", tmp_path / "photos")
    monkeypatch.setenv("SITE_REPORT_STORAGE", str(tmp_path / "photos"))
    monkeypatch.setenv("ENGINEERING_AI_STORAGE", str(tmp_path / "documents"))
    monkeypatch.setenv("ACCEPTANCE_STORAGE", str(tmp_path / "acceptance"))
    monkeypatch.setenv(
        "ACCEPTANCE_TEMPLATE",
        str(Path(__file__).resolve().parents[2] / "data/templates/acceptance-original.xlsx"),
    )
    with factory() as db:
        db.add(
            User(
                username="dod-admin",
                password_hash=password_hash("long-test-password"),
                role="admin",
            )
        )
        db.commit()

    client = TestClient(app)
    headers = _login(client)
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Công trình DOD",
            "client": "Chủ đầu tư DOD",
            "location": "Hải Phòng",
            "report_title": "BÁO CÁO DOD",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    base = f"/api/v1/projects/{project_id}"
    work = client.post(
        f"{base}/work-items",
        headers=headers,
        json={"code": "W-DOD", "name": "Sửa chữa cọc DOD", "location": "Khu A"},
    )
    assert work.status_code == 201, work.text
    other = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Công trình khác", "location": "Nơi khác"},
    )
    assert other.status_code == 201, other.text
    return {
        "client": client,
        "factory": factory,
        "headers": headers,
        "project_id": project_id,
        "other_project_id": other.json()["id"],
        "work_item_id": work.json()["id"],
        "base": base,
        "tmp_path": tmp_path,
    }






def test_system_a_chat_uses_extracted_data_and_persists_conversations(harness):
    client: TestClient = harness["client"]
    headers = harness["headers"]
    base = harness["base"]
    project_id = harness["project_id"]
    other_base = f"/api/v1/projects/{harness['other_project_id']}"

    # Existing sources only: seed one document/page plus one verified AI extraction.
    with harness["factory"]() as db:
        import json

        from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument

        document = SourceDocument(
            id="doc-dod",
            project_id=project_id,
            type="drawing",
            original_name="drawing-dod.pdf",
            document_key="drawing-dod",
            original_path=str(harness["tmp_path"] / "drawing-dod.pdf"),
            sha256="d" * 64,
            status="ready",
            is_current=True,
            is_effective=True,
            page_count=2,
            drawing_number="BV-DOD",
            revision="A",
        )
        pages = [
            DocumentPage(
                id=f"page-dod-{number}",
                project_id=project_id,
                document_id=document.id,
                page_number=number,
                drawing_number="BV-DOD",
                revision="A",
            )
            for number in (1, 2)
        ]
        db.add_all([document, *pages])
        db.add(
            PageExtraction(
                project_id=project_id,
                document_id=document.id,
                page_id="page-dod-2",
                page_number=2,
                model="test",
                prompt_version="test",
                mode="direct",
                status="verified",
                confidence=0.9,
                extraction_json=json.dumps(
                    {
                        "page_type": "drawing",
                        "title": "Anchor length",
                        "drawing_number": "BV-DOD",
                        "revision": "A",
                        "summary": "Anchor length is 50 mm.",
                        "key_values": [
                            {
                                "name": "Anchor length",
                                "value": "50",
                                "unit": "mm",
                                "quote": "Anchor length is 50 mm.",
                            }
                        ],
                        "table_rows": [],
                        "warnings": [],
                        "confidence": 0.9,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    listed = client.get(f"{base}/documents", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["id"] == "doc-dod"

    removed_search = client.post(
        f"{base}/ai/search", headers=headers, json={"query": "Anchor length"}
    )
    assert removed_search.status_code == 404

    first_chat = client.post(
        f"{base}/ai/chat", headers=headers, json={"message": "Anchor length?"}
    )
    assert first_chat.status_code == 200, first_chat.text
    first_body = first_chat.json()
    assert first_body["citations"]
    assert first_body["citations"][0]["page_number"] == 2
    assert first_body["citations"][0]["source"] == "page_extraction"
    assert "50 mm" in first_body["citations"][0]["quote"]
    conversation_id = first_body["conversation_id"]

    second_chat = client.post(
        f"{base}/ai/chat",
        headers=headers,
        json={"message": "Anchor length again", "conversation_id": conversation_id},
    )
    assert second_chat.status_code == 200, second_chat.text
    assert second_chat.json()["message_index"] > first_body["message_index"]
    assert second_chat.json()["citations"]

    isolated = client.post(
        f"{other_base}/ai/chat", headers=headers, json={"message": "Anchor length?"}
    )
    assert isolated.status_code == 200
    assert isolated.json()["citations"] == []
    assert isolated.json()["no_source"] is True

    created = client.post(
        f"{base}/ai/conversations", headers=headers, json={"title": "Hỏi chiều dài neo"}
    )
    assert created.status_code == 201, created.text
    convo_id = created.json()["id"]
    found = client.get(
        f"{base}/ai/conversations", headers=headers, params={"q": "chiều dài"}
    )
    assert found.status_code == 200
    assert any(item["id"] == convo_id for item in found.json())
    renamed = client.patch(
        f"{base}/ai/conversations/{convo_id}",
        headers=headers,
        json={"title": "Chiều dài neo - Rev B"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Chiều dài neo - Rev B"
    assert (
        client.get(f"{base}/ai/conversations/{convo_id}", headers=headers).status_code
        == 200
    )
    deleted = client.delete(f"{base}/ai/conversations/{convo_id}", headers=headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"{base}/ai/conversations/{convo_id}", headers=headers).status_code
        == 404
    )


def test_system_b_is_deterministic_reuses_pyc_and_has_no_ai(harness, monkeypatch):
    client: TestClient = harness["client"]
    headers = harness["headers"]
    base = harness["base"]
    work_item_id = harness["work_item_id"]

    report = client.put(
        f"{base}/daily-reports/2026-11-11",
        headers=headers,
        json={
            "status": "reviewed",
            "manpower": [{"group_name": "Công nhân", "count": 2}],
            "work_logs": [
                {"work_item_id": work_item_id, "location": "Khu A", "status": "done"}
            ],
            "next_day_plans": [],
        },
    )
    assert report.status_code == 200, report.text
    report_id = report.json()["id"]

    request_payload = {
        "work_item_id": work_item_id,
        "daily_report_id": report_id,
        "request_date": "2026-11-11",
        "inspection_time": "15h00",
        "location": "Khu A - Phân đoạn 1",
        "content": "Nghiệm thu sửa chữa cọc DOD",
        "subject": "Cọc DOD",
        "field": "construction",
        "urgency": "normal",
        "requested_by_name": "Nguyễn Văn Yêu Cầu",
        "supervisor_name": "Trần Văn Giám Sát",
        "investor_name": "Lê Văn Chủ Đầu Tư",
        "contractor_org": "Nhà thầu DOD",
        "supervisor_org": "Tư vấn DOD",
        "investor_org": "Chủ đầu tư DOD",
    }
    created = client.post(f"{base}/acceptance-requests", headers=headers, json=request_payload)
    assert created.status_code == 201, created.text
    request = created.json()
    request_id = request["id"]
    assert request["number"]

    # Numbering is deterministic and unique for concurrent-style sequential calls.
    numbers = {request["number"]}
    for _ in range(5):
        response = client.post(
            f"{base}/acceptance-requests", headers=headers, json=request_payload
        )
        assert response.status_code == 201, response.text
        numbers.add(response.json()["number"])
    assert len(numbers) == 6

    preview = client.get(
        f"{base}/acceptance-requests/{request_id}/preview", headers=headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["kind"] == "pyc"
    # The template prints the "Số: YC-" label in A6, so B6 carries only the
    # number body (the stored request number may include its own prefix).
    assert preview.json()["cells"]["PYC"]["B6"] == request["number"].rsplit("-", 1)[-1]

    record_resp = client.post(
        f"{base}/acceptance-records", headers=headers, json={"request_id": request_id}
    )
    assert record_resp.status_code == 201, record_resp.text
    record = record_resp.json()
    assert record["result"] is None
    assert record["status"] == "draft"
    assert {item["state"] for item in record["checklist"]} == {"unconfirmed"}
    assert record["reused"]["work_item_id"] == work_item_id
    assert record["reused"]["location"] == "Khu A - Phân đoạn 1"
    assert {item["person_name"] for item in record["participants"]} >= {
        "Nguyễn Văn Yêu Cầu",
        "Trần Văn Giám Sát",
        "Lê Văn Chủ Đầu Tư",
    }

    record_preview = client.get(
        f"{base}/acceptance-records/{record['id']}/preview", headers=headers
    )
    assert record_preview.status_code == 200, record_preview.text
    assert record_preview.json()["cells"]["BBNT"]["B6"] == "Khu A - Phân đoạn 1"

    # System B must not call the AI answer provider while it creates/exports files.
    import app.engineering_ai.providers as providers

    def _raise(*_args, **_kwargs):
        raise AssertionError("Acceptance must not call AI")

    monkeypatch.setattr(providers, "provider_from_env", _raise)

    exported = client.post(
        f"{base}/acceptance-requests/{request_id}/exports",
        headers=headers,
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert exported.status_code == 201, exported.text
    content = client.get(exported.json()["download_url"], headers=headers).content
    assert content.startswith(b"PK")
    workbook = openpyxl.load_workbook(BytesIO(content))
    assert workbook["PYC"]["B6"].value == request["number"].rsplit("-", 1)[-1]
    assert "Công trình DOD" in str(workbook["PYC"]["C1"].value)

    if shutil.which("libreoffice") or shutil.which("soffice"):
        pdf = client.post(
            f"{base}/acceptance-requests/{request_id}/exports",
            headers=headers,
            json={"kind": "pyc", "format": "pdf"},
        )
        assert pdf.status_code == 201, pdf.text
        assert client.get(pdf.json()["download_url"], headers=headers).content.startswith(b"%PDF")

    # A PYC change marks the issued BBNT stale without auto-editing it.
    patched = client.patch(
        f"{base}/acceptance-requests/{request_id}",
        headers=headers,
        json={"location": "Khu B - Phân đoạn 2"},
    )
    assert patched.status_code == 200, patched.text
    stale = client.get(f"{base}/acceptance-records/{record['id']}", headers=headers)
    assert stale.status_code == 200
    assert stale.json()["stale"] is True
    frozen = client.get(
        f"{base}/acceptance-records/{record['id']}/preview", headers=headers
    )
    assert frozen.status_code == 200
    assert frozen.json()["cells"]["BBNT"]["B6"] == "Khu A - Phân đoạn 1"
    revision = client.post(
        f"{base}/acceptance-records/{record['id']}/revisions", headers=headers
    )
    assert revision.status_code == 201, revision.text
    assert revision.json()["revision"] == 2
    assert revision.json()["supersedes_id"] == record["id"]

    history = client.get(
        f"{base}/work-items/{work_item_id}/acceptance-history", headers=headers
    )
    assert history.status_code == 200, history.text
    kinds = {item["kind"] for item in history.json()["items"]}
    assert {"pyc", "bbnt"} <= kinds
