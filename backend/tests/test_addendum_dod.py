"""End-to-end evidence for the addendum Definition of Done.

This is a coordinator-owned integration test. It uses a temporary database and
storage, never ``data/app.db`` or the user's source workbook.
"""
from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import fitz
import openpyxl
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.models import User
from app.engineering_ai import dependencies as ai_dependencies
from app.main import app
from app.site import service as site_service


def _pdf(pages: list[tuple[str, str]]) -> bytes:
    document = fitz.open()
    for drawing, text in pages:
        page = document.new_page()
        page.insert_text((72, 72), f"{drawing}\n{text}", fontsize=12)
    data = document.tobytes()
    document.close()
    return data


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
    monkeypatch.setattr(ai_dependencies, "_shared_session_factory", factory)
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


def test_system_a_persistent_citations_versions_and_conversations(harness):
    client: TestClient = harness["client"]
    headers = harness["headers"]
    base = harness["base"]
    project_id = harness["project_id"]
    other_base = f"/api/v1/projects/{harness['other_project_id']}"

    version_one = _pdf(
        [
            ("BV-DOD Rev A", "Drawing cover page."),
            ("BV-DOD Rev A", "Anchor length is 50 mm."),
        ]
    )
    upload = client.post(
        f"{base}/documents",
        headers=headers,
        files={"file": ("drawing-dod.pdf", version_one, "application/pdf")},
        data={"type": "drawing"},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]

    document = client.get(f"{base}/documents/{document_id}", headers=headers).json()
    assert document["status"] == "ready"
    assert document["page_count"] == 2
    assert document["is_effective"] is True
    assert Path(document["original_url"]).name  # metadata URL is present

    search = client.post(
        f"{base}/ai/search", headers=headers, json={"query": "Anchor length"}
    )
    assert search.status_code == 200, search.text
    citations = search.json()["citations"]
    assert citations and citations[0]["page_number"] == 2
    assert "50 mm" in citations[0]["quote"]
    assert client.get(citations[0]["url"], headers=headers).status_code == 200

    # The file and text survive a new client/session, without uploading again.
    second_client = TestClient(app)
    second_headers = _login(second_client)
    assert (
        second_client.get(f"{base}/documents/{document_id}", headers=second_headers).status_code
        == 200
    )
    with harness["factory"]() as db:
        from app.engineering_ai.models import SourceDocument

        stored = db.get(SourceDocument, document_id)
        assert stored is not None and Path(stored.original_path).is_file()

    # Chat answers only from AI-extracted structured data, never raw OCR text.
    with harness["factory"]() as db:
        import json

        from app.engineering_ai.models import DocumentPage, PageExtraction

        page = db.query(DocumentPage).filter_by(
            document_id=document_id, page_number=2
        ).one()
        db.add(
            PageExtraction(
                project_id=project_id,
                document_id=document_id,
                page_id=page.id,
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

    first_chat = client.post(
        f"{base}/ai/chat", headers=headers, json={"message": "Anchor length?"}
    )
    assert first_chat.status_code == 200, first_chat.text
    assert first_chat.json()["citations"]
    conversation_id = first_chat.json()["conversation_id"]
    second_chat = client.post(
        f"{base}/ai/chat",
        headers=headers,
        json={"message": "Anchor length again", "conversation_id": conversation_id},
    )
    assert second_chat.status_code == 200, second_chat.text
    assert second_chat.json()["message_index"] > first_chat.json()["message_index"]
    assert second_chat.json()["citations"]

    # Revision B is uploaded but is not effective until a manager confirms it.
    version_two = _pdf(
        [
            ("BV-DOD Rev B", "Drawing cover page."),
            ("BV-DOD Rev B", "Anchor length is 60 mm."),
        ]
    )
    revision = client.post(
        f"{base}/documents",
        headers=headers,
        files={"file": ("drawing-dod.pdf", version_two, "application/pdf")},
        data={"type": "drawing", "change_note": "Rev B - cập nhật chiều dài neo"},
    )
    assert revision.status_code == 201, revision.text
    revision_id = revision.json()["id"]
    revision_doc = client.get(f"{base}/documents/{revision_id}", headers=headers).json()
    assert revision_doc["version"] == 2
    assert revision_doc["is_effective"] is False
    assert revision_doc["change_note"] == "Rev B - cập nhật chiều dài neo"
    versions = client.get(
        f"{base}/documents/{revision_id}/versions", headers=headers
    ).json()
    assert {item["version"] for item in versions} == {1, 2}
    still_one = client.post(
        f"{base}/ai/search", headers=headers, json={"query": "Anchor length"}
    ).json()["citations"]
    assert still_one and all("50 mm" in item["quote"] for item in still_one)

    activated = client.post(
        f"{base}/documents/{revision_id}/effective",
        headers=headers,
        json={"change_note": "Rev B được duyệt"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["is_effective"] is True
    current = client.post(
        f"{base}/ai/search", headers=headers, json={"query": "Anchor length"}
    ).json()["citations"]
    assert current and "60 mm" in current[0]["quote"]
    history = client.post(
        f"{base}/ai/search",
        headers=headers,
        json={"query": "Anchor length", "scope": "history"},
    ).json()["citations"]
    assert any(item["version"] == 2 for item in history)

    compare = client.get(
        f"{base}/documents/{revision_id}/compare/{document_id}", headers=headers
    )
    assert compare.status_code == 200, compare.text
    assert compare.json()["left"]["version"] == 2
    assert compare.json()["right"]["version"] == 1

    # Old revision files remain readable and project isolation is enforced.
    assert client.get(f"{base}/documents/{document_id}/original", headers=headers).status_code == 200
    assert (
        client.get(f"{other_base}/documents/{document_id}", headers=headers).status_code == 404
    )
    empty = client.post(
        f"{other_base}/ai/search", headers=headers, json={"query": "Anchor length"}
    )
    assert empty.status_code == 200
    assert empty.json()["citations"] == []

    # Conversation management: create, search, rename, reopen and delete.
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


def test_real_ocr_pipeline_indexes_scanned_page(harness, monkeypatch):
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract binary not installed")
    client: TestClient = harness["client"]
    headers = harness["headers"]
    base = harness["base"]
    monkeypatch.setenv("ENGINEERING_AI_OCR_LANGUAGES", "eng")
    monkeypatch.setenv("ENGINEERING_AI_OCR_ENGINE", "tesseract")

    font_path = next(
        (
            path
            for path in (
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
                Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
            )
            if path.is_file()
        ),
        None,
    )
    if font_path is None:
        pytest.skip("No TrueType font for the scan fixture")
    image = Image.new("RGB", (1800, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (60, 140),
        "ANCHOR LENGTH 50 MM",
        fill="black",
        font=ImageFont.truetype(str(font_path), 110),
    )
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    scanned = fitz.open()
    page = scanned.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(30, 60, 565, 240), stream=image_bytes.getvalue())
    data = scanned.tobytes()
    scanned.close()

    upload = client.post(
        f"{base}/documents",
        headers=headers,
        files={"file": ("scan-dod.pdf", data, "application/pdf")},
        data={"type": "drawing"},
    )
    assert upload.status_code == 201, upload.text
    document = client.get(
        f"{base}/documents/{upload.json()['id']}", headers=headers
    ).json()
    assert document["status"] == "ready"
    page_detail = client.get(
        f"{base}/documents/{document['id']}/pages/1", headers=headers
    ).json()
    assert page_detail["extraction_method"] == "ocr"
    assert "ANCHOR" in (page_detail["text"] or "").upper()
    assert "50" in (page_detail["text"] or "")
    assert page_detail["ocr_confidence"] is not None
    found = client.post(
        f"{base}/ai/search", headers=headers, json={"query": "ANCHOR LENGTH"}
    )
    assert found.status_code == 200
    assert found.json()["citations"]


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

    # System B must not call any AI provider while it creates and exports files.
    import app.engineering_ai.embeddings as embeddings
    import app.engineering_ai.providers as providers
    import app.engineering_ai.vision as vision

    def _raise(*_args, **_kwargs):
        raise AssertionError("Acceptance must not call AI")

    monkeypatch.setattr(providers, "provider_from_env", _raise)
    monkeypatch.setattr(vision, "vision_from_env", _raise)
    monkeypatch.setattr(embeddings, "embeddings_from_env", _raise)

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
