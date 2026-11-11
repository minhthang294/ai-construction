"""One synthetic project through the mounted routers and shared database."""

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import fitz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import access, auth, database
from app.core.auth import password_hash
from app.core.models import User
from app.main import app
from app.site import service as site_service
from app.engineering_ai import dependencies as ai_dependencies


def test_project_report_photo_ai_and_acceptance(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    for module in (database, auth, access):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(site_service, "STORAGE_ROOT", tmp_path / "photos")
    monkeypatch.setattr(ai_dependencies, "_shared_session_factory", factory)
    monkeypatch.setenv("ENGINEERING_AI_STORAGE", str(tmp_path / "documents"))
    monkeypatch.setenv("ACCEPTANCE_STORAGE", str(tmp_path / "acceptance"))
    monkeypatch.setenv(
        "ACCEPTANCE_TEMPLATE",
        str(Path(__file__).resolve().parents[2] / "data/templates/acceptance-original.xlsx"),
    )
    with factory() as db:
        db.add(User(username="workflow-admin", password_hash=password_hash("long-test-password"), role="admin"))
        db.commit()

    client = TestClient(app)
    token = client.post("/api/v1/auth/login", json={"username": "workflow-admin", "password": "long-test-password"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Công trình thử nghiệm", "report_title": "BÁO CÁO CÔNG VIỆC THỬ NGHIỆM"})
    assert project.status_code == 201, project.text
    base = f"/api/v1/projects/{project.json()['id']}"
    work = client.post(f"{base}/work-items", headers=headers, json={"code": "W1", "name": "Trám vá cấu kiện thử nghiệm"})
    assert work.status_code == 201, work.text
    work_id = work.json()["id"]

    report = client.put(f"{base}/daily-reports/2026-11-11", headers=headers, json={
        "status": "reviewed",
        "manpower": [{"group_name": "Công nhân", "count": 2}, {"group_name": "Lái xe", "count": 0}],
        "work_logs": [{"work_item_id": work_id, "location": "Khu thử nghiệm", "status": "done"}],
        "next_day_plans": [{"plan_date": "2026-11-12", "work_item_id": work_id, "description": "Kiểm tra cấu kiện"}],
    })
    assert report.status_code == 200, report.text
    assert report.json()["manpower"][1]["count"] == 0

    photo_bytes = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(photo_bytes, format="PNG")
    photo = client.post(f"{base}/photos", headers=headers,
        files={"files": ("test.png", photo_bytes.getvalue(), "image/png")},
        data={"report_id": report.json()["id"], "confirmed_caption": "Ảnh cấu kiện thử nghiệm", "work_item_ids": work_id})
    assert photo.status_code == 201, photo.text
    photo_id = photo.json()[0]["id"]

    export = client.post(f"{base}/daily-reports/2026-11-11/exports", headers=headers, json={"format": "zalo"})
    assert export.status_code == 201, export.text
    assert "Trám vá cấu kiện thử nghiệm" in export.json()["preview_text"]
    assert client.get(export.json()["download_url"], headers=headers).status_code == 200
    pdf = client.post(f"{base}/daily-reports/2026-11-11/exports", headers=headers, json={"format": "pdf"})
    assert pdf.status_code == 201, pdf.text
    assert client.get(pdf.json()["download_url"], headers=headers).content.startswith(b"%PDF")

    missing = client.post(f"{base}/ai/chat", headers=headers, json={"message": "Thông số thiết kế của cọc là gì?"})
    assert missing.status_code == 200, missing.text
    assert missing.json()["citations"] == []
    assert "Không tìm thấy" in missing.json()["answer"]

    pdf_bytes = fitz.open()
    page = pdf_bytes.new_page()
    page.insert_text((72, 72), "Synthetic drawing BV-TEST. Anchor length is 50 mm.")
    source = client.post(f"{base}/documents", headers=headers,
        files={"file": ("synthetic-drawing.pdf", pdf_bytes.tobytes(), "application/pdf")})
    pdf_bytes.close()
    assert source.status_code == 201, source.text
    search = client.post(f"{base}/ai/search", headers=headers, json={"query": "Anchor length"})
    assert search.status_code == 200, search.text
    assert search.json()["citations"][0]["page_number"] == 1
    assert search.json()["citations"][0]["document_id"] == source.json()["id"]
    page_id = client.get(f"{base}/documents/{source.json()['id']}", headers=headers).json()["pages"][0]["id"]
    draft = client.post(f"{base}/ai/daily-report-drafts", headers=headers, json={"report_id": report.json()["id"]})
    assert draft.status_code == 200, draft.text
    assert draft.json()["no_invented_quantities"] is True
    assert draft.json()["draft"]["work_logs"][0]["quantity"] is None
    suggestions = client.post(f"{base}/ai/inspection-checklists", headers=headers,
        json={"work_item_id": work_id, "focus": "Anchor length"})
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()["suggestions"]
    assert all(item["status"] == "unconfirmed" and item["citation"]["page_number"] == 1
               for item in suggestions.json()["suggestions"])

    request = client.post(f"{base}/acceptance-requests", headers=headers, json={
        "number": "PYC-TEST-1", "work_item_id": work_id, "daily_report_id": report.json()["id"],
        "request_date": "2026-11-11", "location": "Khu thử nghiệm",
        "content": "Nghiệm thu công việc thử nghiệm", "field": "construction", "urgency": "normal",
    })
    assert request.status_code == 201, request.text
    assert request.json()["project_name"] == "Công trình thử nghiệm"
    assert request.json()["daily_report_id"] == report.json()["id"]
    pyc = client.post(f"{base}/acceptance-requests/{request.json()['id']}/exports", headers=headers, json={"kind": "pyc", "format": "xlsx"})
    assert pyc.status_code == 201, pyc.text
    assert client.get(pyc.json()["download_url"], headers=headers).content.startswith(b"PK")
    assert [item["kind"] for item in client.get(f"{base}/acceptance-exports", headers=headers).json()] == ["pyc"]
    assert client.get(f"{base}/acceptance-exports/{pdf.json()['id']}/download", headers=headers).status_code == 404
    assert client.get(f"{base}/generated-documents/{pyc.json()['id']}/download", headers=headers).status_code == 404

    record = client.post(f"{base}/acceptance-records", headers=headers, json={"request_id": request.json()["id"]})
    assert record.status_code == 201, record.text
    record_id = record.json()["id"]
    evidence = [[photo_id], [f"document:{source.json()['id']}"], [f"page:{page_id}"]]
    checklist = [{"item": item["item"], "state": "yes", "evidence_refs": evidence[index] if index < len(evidence) else []}
                 for index, item in enumerate(record.json()["checklist"])]
    updated = client.patch(f"{base}/acceptance-records/{record_id}", headers=headers,
        json={"design_compliance": "yes", "technical_compliance": "yes", "checklist": checklist})
    assert updated.status_code == 200, updated.text
    confirmed = client.post(f"{base}/acceptance-records/{record_id}/confirm", headers=headers, json={"result": "approved"})
    assert confirmed.status_code == 200, confirmed.text
    bbnt = client.post(f"{base}/acceptance-records/{record_id}/exports", headers=headers, json={"kind": "bbnt", "format": "xlsx"})
    assert bbnt.status_code == 201, bbnt.text
    assert client.get(bbnt.json()["download_url"], headers=headers).content.startswith(b"PK")
