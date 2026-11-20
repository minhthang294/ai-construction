from .conftest import make_scanned_pdf, upload_pdf
from fastapi import HTTPException

from app.engineering_ai.dependencies import project_editor_access
from app.engineering_ai.models import PageExtraction


def _extraction(text="Lớp bảo vệ 50 mm"):
    return {
        "page_type": "drawing",
        "title": "Bản vẽ trụ",
        "drawing_number": "BV-01",
        "revision": "A",
        "summary": "Trang bản vẽ kết cấu trụ.",
        "key_values": [
            {
                "name": "Lớp bảo vệ",
                "value": "50",
                "unit": "mm",
                "quote": text,
            }
        ],
        "table_rows": [["Hạng mục", "Giá trị"], ["Lớp bảo vệ", "50"]],
        "warnings": ["Cần đối chiếu bản gốc."],
        "confidence": 0.8,
    }


def _post_extraction(client, document_id, page=1, extraction=None, **overrides):
    body = {
        "model": "deepseek-v4.1-flash",
        "prompt_version": "poc-v1",
        "mode": "tile",
        "extraction": extraction if extraction is not None else _extraction(),
        "confidence": 0.8,
        "warnings": ["AI extraction cần kiểm tra."],
    }
    body.update(overrides)
    return client.post(
        f"/api/v1/projects/p1/documents/{document_id}/pages/{page}/extractions",
        json=body,
    )


def test_save_upsert_and_verify_page_extraction(client, digital_document):
    first = _post_extraction(client, digital_document["id"])
    assert first.status_code == 200, first.text
    body = first.json()
    extraction_id = body["id"]
    assert body["status"] == "proposed"
    assert body["page_number"] == 1
    assert body["page_sha256"] is None  # native page has no rendered image
    assert body["created_by"] == "test-user"
    assert body["extraction"]["key_values"][0]["value"] == "50"

    changed = _extraction("Bản sửa 75 mm")
    changed["summary"] = "Bản sửa đổi"
    second = _post_extraction(
        client,
        digital_document["id"],
        extraction=changed,
        confidence=0.61,
        warnings=["Đã chạy lại tile."],
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == extraction_id  # upsert by unique key
    assert second.json()["confidence"] == 0.61
    assert second.json()["status"] == "proposed"
    assert second.json()["extraction"]["summary"] == "Bản sửa đổi"

    listed = client.get(
        f"/api/v1/projects/p1/documents/{digital_document['id']}/extractions",
        params={"page": 1, "status": "proposed"},
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == extraction_id

    fetched = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == extraction_id

    verified = client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "verified", "note": "Đã đối chiếu bản gốc."},
    )
    assert verified.status_code == 200, verified.text
    verified_body = verified.json()
    assert verified_body["status"] == "verified"
    assert verified_body["verified_by"] == "test-user"
    assert verified_body["verified_at"]
    assert verified_body["verify_note"] == "Đã đối chiếu bản gốc."

    rejected = client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "rejected", "note": "Số liệu chưa khớp."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_verified_extraction_is_not_overwritten_by_same_version(client, digital_document):
    saved = _post_extraction(client, digital_document["id"]).json()
    extraction_id = saved["id"]
    original_summary = saved["extraction"]["summary"]
    verified = client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "verified", "note": "Đã đối chiếu bản gốc."},
    )
    assert verified.status_code == 200, verified.text

    altered = _extraction("Bản sửa 75 mm")
    altered["summary"] = "Bản sửa đổi"
    conflict = _post_extraction(
        client, digital_document["id"], extraction=altered, confidence=0.3
    )
    assert conflict.status_code == 409, conflict.text

    current = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}").json()
    assert current["status"] == "verified"
    assert current["confidence"] == 0.8
    assert current["extraction"]["summary"] == original_summary
    assert current["extraction"]["key_values"][0]["value"] == "50"
    assert current["verified_by"] == "test-user"
    assert current["verify_note"] == "Đã đối chiếu bản gốc."

    new_version = _post_extraction(
        client,
        digital_document["id"],
        extraction=altered,
        confidence=0.3,
        prompt_version="poc-v2",
    )
    assert new_version.status_code == 200, new_version.text
    assert new_version.json()["id"] != extraction_id
    kept = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}").json()
    assert kept["status"] == "verified"
    assert kept["extraction"]["summary"] == original_summary


def test_page_extraction_scope_and_invalid_schema(client, digital_document):
    wrong_page = _post_extraction(client, digital_document["id"], page=99)
    assert wrong_page.status_code == 404

    wrong_document = client.get(
        "/api/v1/projects/p1/documents/not-a-document/extractions"
    )
    assert wrong_document.status_code == 404

    invalid = _post_extraction(
        client,
        digital_document["id"],
        extraction={"page_type": "drawing", "summary": 3, "key_values": []},
    )
    assert invalid.status_code == 422

    created = _post_extraction(client, digital_document["id"]).json()
    cross_get = client.get(
        f"/api/v1/projects/p2/page-extractions/{created['id']}"
    )
    assert cross_get.status_code == 404
    cross_patch = client.patch(
        f"/api/v1/projects/p2/page-extractions/{created['id']}",
        json={"status": "verified"},
    )
    assert cross_patch.status_code == 404
    cross_list = client.get(
        f"/api/v1/projects/p2/documents/{digital_document['id']}/extractions"
    )
    assert cross_list.status_code == 404


def test_extraction_uses_rendered_page_hash_and_does_not_feed_retrieval(
    client, ocr_engine, digital_document
):
    from app.engineering_ai.ocr import OcrResult

    ocr_engine.result = OcrResult(
        text="Trang scan có lớp bảo vệ 50 mm.",
        confidence=0.9,
        engine="mock-ocr",
    )
    scanned = upload_pdf(client, filename="extraction-scan.pdf", data=make_scanned_pdf())
    assert scanned.status_code == 201, scanned.text
    body = _post_extraction(client, scanned.json()["id"]).json()
    assert body["page_sha256"] and len(body["page_sha256"]) == 64

    # A unique token present only in the AI extraction must not become page text
    # or a retrieval citation.
    extraction = _extraction("ZZINVENTED-TOKEN")
    extraction["summary"] = "ZZINVENTED-TOKEN"
    stored = _post_extraction(
        client,
        scanned.json()["id"],
        extraction=extraction,
        mode="full-page",
    )
    assert stored.status_code == 200
    search = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "ZZINVENTED-TOKEN"},
    ).json()
    assert search["has_sources"] is False


def test_extraction_route_does_not_call_ai_provider(client, monkeypatch, digital_document):
    import app.engineering_ai.providers as providers
    import app.engineering_ai.vision as vision

    def fail(*args, **kwargs):
        raise AssertionError("AI provider must not be called")

    monkeypatch.setattr(providers, "provider_from_env", fail)
    monkeypatch.setattr(vision, "vision_from_env", fail)
    response = _post_extraction(client, digital_document["id"])
    assert response.status_code == 200, response.text


def test_page_extraction_write_requires_editor(client, digital_document):
    app = client.app
    previous = app.dependency_overrides[project_editor_access]

    def deny_viewer(project_id):
        raise HTTPException(403, "Insufficient project role")

    app.dependency_overrides[project_editor_access] = deny_viewer
    try:
        assert _post_extraction(client, digital_document["id"]).status_code == 403
        assert client.get(
            f"/api/v1/projects/p1/documents/{digital_document['id']}/extractions"
        ).status_code == 200
    finally:
        app.dependency_overrides[project_editor_access] = previous


def test_reingest_keeps_verified_extraction_on_unchanged_page(
    client, digital_document, session_factory
):
    saved = _post_extraction(client, digital_document["id"]).json()
    extraction_id, page_id = saved["id"], saved["page_id"]
    verified = client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "verified", "note": "Đã đối chiếu."},
    )
    assert verified.status_code == 200

    retry = client.post(
        f"/api/v1/projects/p1/documents/{digital_document['id']}/reingest"
    )
    assert retry.status_code == 202, retry.text
    fetched = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}")
    assert fetched.status_code == 200
    assert fetched.json()["page_id"] == page_id
    assert fetched.json()["status"] == "verified"
    with session_factory() as db:
        assert db.query(PageExtraction).filter(PageExtraction.id == extraction_id).count() == 1


def test_reingest_changed_render_invalidates_verified_extraction(
    client, ocr_engine, monkeypatch
):
    from app.engineering_ai.ocr import OcrResult
    import app.engineering_ai.service as service
    from pathlib import Path

    ocr_engine.result = OcrResult(text="Cọc F27 đục sâu 1 cm", confidence=0.9, engine="mock")
    document = upload_pdf(client, data=make_scanned_pdf()).json()
    saved = _post_extraction(client, document["id"]).json()
    extraction_id = saved["id"]
    client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "verified"},
    )
    original = service.extract_document

    def changed_render(*args, **kwargs):
        result = original(*args, **kwargs)
        Path(result.pages[0].rendered_path).write_bytes(b"changed-render")
        return result

    monkeypatch.setattr(service, "extract_document", changed_render)
    retry = client.post(f"/api/v1/projects/p1/documents/{document['id']}/reingest")
    assert retry.status_code == 202
    fetched = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}").json()
    assert fetched["status"] == "proposed"
    assert fetched["verified_by"] is None


def test_reingest_missing_page_preserves_extraction_and_fails_job(
    client, digital_document, monkeypatch
):
    import app.engineering_ai.service as service

    saved = _post_extraction(client, digital_document["id"], page=2).json()
    extraction_id = saved["id"]
    client.patch(
        f"/api/v1/projects/p1/page-extractions/{extraction_id}",
        json={"status": "verified"},
    )
    original = service.extract_document

    def missing_page(*args, **kwargs):
        result = original(*args, **kwargs)
        result.pages = result.pages[:1]
        result.page_count = 1
        return result

    monkeypatch.setattr(service, "extract_document", missing_page)
    retry = client.post(f"/api/v1/projects/p1/documents/{digital_document['id']}/reingest")
    assert retry.status_code == 202
    detail = client.get(f"/api/v1/projects/p1/documents/{digital_document['id']}").json()
    assert detail["status"] == "ready"
    assert detail["error_message"]
    fetched = client.get(f"/api/v1/projects/p1/page-extractions/{extraction_id}").json()
    assert fetched["status"] == "verified"
    assert fetched["page_id"] == saved["page_id"]
