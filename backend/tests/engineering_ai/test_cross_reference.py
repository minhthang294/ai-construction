from .conftest import make_scanned_pdf, make_text_pdf, upload_pdf


def _cross_reference(client, project_id, first, second, topic=None):
    body = {
        "first": {"document_id": first["id"], "page_number": 1},
        "second": {"document_id": second["id"], "page_number": 1},
    }
    if topic:
        body["topic"] = topic
    return client.post(
        f"/api/v1/projects/{project_id}/ai/cross-references",
        json=body,
    )


def _upload_pair(client, first_text, second_text, first_name="first.pdf", second_name="second.pdf"):
    first = upload_pdf(client, filename=first_name, data=make_text_pdf([first_text]))
    second = upload_pdf(client, filename=second_name, data=make_text_pdf([second_text]))
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    return first.json(), second.json()


def test_cross_reference_flags_numeric_difference_with_two_citations(client):
    first, second = _upload_pair(
        client,
        "Concrete cover for abutment is 50 mm.",
        "Concrete cover for abutment is 60 mm.",
    )
    response = _cross_reference(client, "p1", first, second, topic="concrete cover abutment")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_engineer_review"
    assert len(body["citations"]) == 2
    assert body["citations"][0]["document_id"] == first["id"]
    assert body["citations"][1]["document_id"] == second["id"]
    assert body["suggestions"], body
    suggestion = body["suggestions"][0]
    assert suggestion["requires_engineer_review"] is True
    assert suggestion["first_citation"]["quote"] == "Concrete cover for abutment is 50 mm."
    assert suggestion["second_citation"]["quote"] == "Concrete cover for abutment is 60 mm."
    assert "50 mm" in suggestion["observation"]
    assert "60 mm" in suggestion["observation"]
    assert "không kết luận" in suggestion["observation"]
    assert "không kết luận" in body["disclaimer"]
    assert body["disclaimer"]
    assert suggestion["first_citation"]["url"].endswith("/pages/1")
    assert suggestion["second_citation"]["url"].endswith("/pages/1")


def test_cross_reference_same_value_returns_no_finding_without_consistency_claim(client):
    first, second = _upload_pair(
        client,
        "Concrete cover for abutment is 50 mm.",
        "Concrete cover for abutment is 50 mm.",
    )
    response = _cross_reference(client, "p1", first, second)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suggestions"] == []
    assert len(body["citations"]) == 2
    assert "không kết luận" in body["message"]
    assert "đồng nhất" in body["message"]
    assert body["status"] == "needs_engineer_review"


def test_cross_reference_is_project_scoped(client):
    first, second = _upload_pair(
        client,
        "Concrete cover for abutment is 50 mm.",
        "Concrete cover for abutment is 60 mm.",
    )
    response = _cross_reference(client, "p2", first, second)
    assert response.status_code == 404


def test_cross_reference_rejects_same_page(client):
    first, _second = _upload_pair(
        client,
        "Concrete cover for abutment is 50 mm.",
        "Concrete cover for abutment is 60 mm.",
    )
    response = client.post(
        "/api/v1/projects/p1/ai/cross-references",
        json={
            "first": {"document_id": first["id"], "page_number": 1},
            "second": {"document_id": first["id"], "page_number": 1},
        },
    )
    assert response.status_code == 422


def test_cross_reference_low_ocr_caps_confidence_and_warns(client, ocr_engine):
    from app.engineering_ai.ocr import OcrResult

    ocr_engine.result = OcrResult(
        text="Concrete cover for abutment is 50 mm.",
        confidence=0.30,
        engine="mock-ocr",
    )
    first = upload_pdf(client, filename="scan-first.pdf", data=make_scanned_pdf())
    assert first.status_code == 201, first.text
    ocr_engine.result = OcrResult(
        text="Concrete cover for abutment is 60 mm.",
        confidence=0.31,
        engine="mock-ocr",
    )
    second = upload_pdf(client, filename="scan-second.pdf", data=make_scanned_pdf())
    assert second.status_code == 201, second.text

    response = _cross_reference(client, "p1", first.json(), second.json())
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc." in body["warnings"]
    assert body["suggestions"]
    assert body["suggestions"][0]["confidence"] <= 0.40
    assert "Thông tin chưa đủ độ tin cậy, cần kiểm tra trực tiếp bản vẽ gốc." in body["suggestions"][0]["warnings"]
